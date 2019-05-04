import sqlite3, atexit, re, json, sys, rpyc, os, time

from datetime import datetime
from rpyc.utils.classic import obtain
from enum import Enum
from uuid import UUID
from multiprocessing import Process
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.meta import CuteMeta, Rating

import logging

# Type conversions
sqlite3.register_adapter(UUID, lambda uid: str(uid.hex))
sqlite3.register_converter("UUID", lambda v: UUID(hex = v.decode()))
sqlite3.register_adapter(Rating, lambda enum: enum.value)
sqlite3.register_converter("Rating", lambda v: Rating(v.decode()))
sqlite3.register_adapter(set, lambda s: json.dumps(list(s)))
sqlite3.register_converter("PSet", lambda v: set(json.loads(v.decode())))

log = logging.Logger("db")
log.addHandler(logging.StreamHandler(sys.stdout))

__hashes: HashTree = None
__db: sqlite3.Connection = None
__rpccon = None

_functions = {}
def dbfun(fun):
    def wrapper(*args, **kwargs):
        global __rpccon
        if __rpccon is None:
            try: 
                __rpccon = rpyc.connect("localhost", config.service_port, config = {
                    "allow_public_attrs": True,
                    "allow_pickle": True
                }).root
            except: 
                __rpccon = False
                log.warn("No database service running, please consider starting it by running cutespam-db in a separate process or setting it up as a service with your system.")
                log.warn("Loading the database takes a long time but it makes the requests a lot faster.")
                init_db()
        
        if __rpccon:
            return obtain(getattr(__rpccon, fun.__name__)(*args, **kwargs))
        else:
            return fun(*args, **kwargs)

    _functions[fun.__name__] = fun
    return wrapper

def regexp(expr, item):
    reg = re.compile(expr)
    return reg.search(item) is not None

def connect_db(metadbf):
    db = sqlite3.connect(str(metadbf), detect_types = sqlite3.PARSE_DECLTYPES)
    db.create_function("REGEXP", 2, regexp)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    log.info("Scanning database")

    metadbf = config.cache_folder / "metadata.db"
    hashdbf = config.cache_folder / "hashes.db"

    refresh_cache = False
    if not metadbf.exists() or not hashdbf.exists():
        metadbf.touch(exist_ok = True)
        refresh_cache = True

    log.info("Setting up database %r", metadbf)

    global __db
    __db = connect_db(metadbf)
    __db.executescript(f"""
        CREATE TABLE IF not EXISTS Metadata (
            uid UUID PRIMARY KEY not null,
            last_updated timestamp not null DEFAULT(strftime('%Y-%m-%d %H:%M:%f', 'now')),
            hash TEXT not null,
            caption TEXT,
            author TEXT,
            source TEXT,
            group_id UUID,
            date timestamp not null DEFAULT(strftime('%Y-%m-%d %H:%M:%f', 'now')),
            rating Rating,
            source_other PSet,
            source_via PSet
        ) WITHOUT ROWID;

        CREATE TABLE IF not EXISTS Metadata_Keywords (
            uid UUID not null,
            keyword TEXT NOT NULL CHECK (keyword REGEXP '{config.tag_regex}')
        );

        CREATE TABLE IF not EXISTS Metadata_Collections (
            uid UUID not null,
            collection TEXT NOT NULL CHECK (collection REGEXP '{config.tag_regex}')
        );
    """)

    if refresh_cache:
        __hashes = HashTree(config.hash_length)

        log.info("Loading folder %r into database", config.image_folder)

        for image in config.image_folder.glob("*.*"):
            if not image.is_file(): continue
                
            log.debug("Loading %r", image)
            meta: CuteMeta = CuteMeta.from_file(image)
            if not meta.uid: continue
            if not meta.hash: continue

            try: __hashes.add(meta.hash)
            except KeyError: log.warn('Possible duplicate "%s"', image)

            __db.execute(f"""
                INSERT INTO Metadata (
                    uid, hash, caption, author, source, group_id, rating, source_other, source_via
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""", (
                    meta.uid, 
                    meta.hash, 
                    meta.caption, 
                    meta.author,
                    meta.source, 
                    meta.group_id,
                    meta.rating, 
                    meta.source_other, 
                    meta.source_via
                )
            )
            if meta.date:
                __db.execute("""
                    UPDATE Metadata SET date = ? WHERE uid is ?
                """, (meta.date, meta.uid))

            if meta.keywords:
                __db.executemany(f"""
                   INSERT INTO Metadata_Keywords VALUES (
                       ?, ?
                   ) 	
                """, [(meta.uid, keyword) for keyword in meta.keywords])
            if meta.collections:
                __db.executemany(f"""
                   INSERT INTO Metadata_Collections VALUES (
                       ?, ?
                   ) 	
                """, [(meta.uid, collection) for collection in meta.collections])

        __db.commit()
        with open(hashdbf, "wb") as hashdbfp:
            log.info("Writing to file...")
            __hashes.write_to_file(hashdbf)

    else:
        with open(hashdbf, "rb") as hashdbfp:
            log.info("Loading hashes from cache %r", hashdbf)
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)

    log.info("Done!")
    def exit():
        __db.commit()
        __db.close()

    atexit.register(exit)

def start_listeners():
    metadbf = config.cache_folder / "metadata.db"

    log.info("Listening for file changes")
    db_listener = Process(target = listen_for_db_changes, args = (metadbf,))
    db_listener.name = "Database change listener"
    db_listener.daemon = True
    db_listener.start()
    file_listener = Process(target = listen_for_file_changes, args = (metadbf,))
    file_listener.name = "File change listener"
    file_listener.daemon = True
    file_listener.start()


def listen_for_file_changes(metadbf: Path):
    db = connect_db(metadbf)

    class EventHandler(FileSystemEventHandler):
        # TODO: Implement deleting and creation
        def on_modified(self, event):
            image = event.src_path
            f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(image))
            meta = CuteMeta.from_file(image)
            data = db.execute("""
                select last_updated from Metadata where uid is ?
            """, (meta.uid,)).fetchone()
            if data["last_updated"] > f_last_updated:
                log.info("Reading from file %r", str(image))
                _save_meta(meta, db)

    file_observer = Observer()
    file_observer.schedule(EventHandler, str(config.image_folder.resolve()))
    file_observer.setDaemon(True)
    file_observer.start()

    while True: time.sleep(10) # Zzzzzzz....

def listen_for_db_changes(metadbf: Path):
    last_updated = os.path.getmtime(metadbf.resolve())
    # We need our own connection since this is on a different thread
    db = connect_db(metadbf) 
    while True:
        time.sleep(10)
        dt_last_updated = datetime.utcfromtimestamp(last_updated).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        modified = db.execute("""
            select * from Metadata where last_updated > ?
        """, (dt_last_updated,)).fetchall()

        for data in modified:
            filename = filename_for_uid(data["uid"])
            f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(filename))
            if data["last_updated"] > f_last_updated:
                meta = CuteMeta.from_file(filename)
                log.info("Writing to file %r", str(meta.filename))

                for name, v in zip(data.keys(), data):
                    setattr(meta, name, v)

                keywords = db.execute("""
                    select keyword from Metadata_Keywords where uid = ?
                """, (data["uid"],)).fetchmany()
                collections = db.execute("""
                    select collection from Metadata_Collections where uid = ?
                """, (data["uid"],)).fetchmany()

                meta.keywords = set(k[0] for k in keywords)
                meta.collections = set(c[0] for c in collections)

                meta.write()

        last_updated = time.time()

def filename_for_uid(uid):
    if isinstance(uid, str):
        uid = UUID(str)

    filename = config.image_folder / str(uid)
    filename = filename.with_suffix(".jpg")
    if filename.exists(): return filename
    filename = filename.with_suffix(".png")
    if filename.exists(): return filename
    filename = filename.with_suffix(".jpeg")
    if filename.exists(): return filename
    
    raise FileNotFoundError("No file for uuid %s found", uid)

@dbfun
def get_tab_complete_uids(uidstr: str):
    uidstr = uidstr.replace("-", "")
    """ Returns a list of tab completions for a starting uid """
    uids = __db.execute("select uid from Metadata where uid like ?", (uidstr + "%",)).fetchall()
    return [uid[0] for uid in uids]

@dbfun
def get_meta(uid: UUID):
    meta = CuteMeta(uid = uid, filename = filename_for_uid(uid))
    res = __db.execute("select * from Metadata where uid is ?", (str(uid.hex),)).fetchone()
    for name, v in zip(res.keys(), res):
        setattr(meta, name, v)
    return meta

@dbfun
def save_meta(meta: CuteMeta):
    _save_meta(meta, __db)

def _save_meta(meta: CuteMeta, db: sqlite3.Connection):
    db.execute("""
        UPDATE Metadata SET
            last_updated = strftime('%Y-%m-%d %H:%M:%f', 'now'),
            hash = ?,
            caption = ?,
            author = ?,
            source = ?,
            group_id = ?,
            rating = ?,
            source_other = ?,
            source_via = ?
        WHERE
            uid is ?
    """, (
        meta.hash,
        meta.caption,
        meta.author,
        meta.source,
        meta.group_id,
        meta.rating,
        meta.source_other,
        meta.source_via,

        meta.uid
    ))

    db.execute("""
        DELETE FROM Metadata_Keywords WHERE uid is ?
    """, (meta.uid,))
    db.execute("""
        DELETE FROM Metadata_Collections WHERE uid is ?
    """, (meta.uid,))


    if meta.keywords:
        db.executemany(f"""
            INSERT INTO Metadata_Keywords VALUES (
                ?, ?
            ) 	
        """, [(meta.uid, keyword) for keyword in meta.keywords])
    if meta.collections:
        db.executemany(f"""
            INSERT INTO Metadata_Collections VALUES (
                ?, ?
            ) 	
        """, [(meta.uid, collection) for collection in meta.collections])
    
    db.commit()

@dbfun
def find_similar_images(uid, threshold, limit = 10):
    """ returns a list of uids for similar images for an image/uid """
    if isinstance(uid, str):
        uid = UUID(str)
