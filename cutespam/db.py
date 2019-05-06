import sqlite3, atexit, re, json, sys, rpyc, os, time
import logging

from datetime import datetime
from rpyc.utils.classic import obtain
from enum import Enum
from uuid import UUID
from multiprocessing import Process
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from math import floor

from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.meta import CuteMeta, Rating

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
            except Exception as e:
                print(str(e)) 
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
    global __db, __hashes

    log.info("Scanning database")

    metadbf = config.cache_folder / "metadata.db"
    hashdbf = config.cache_folder / "hashes.db"

    refresh_cache = False
    if not metadbf.exists() or not hashdbf.exists():
        metadbf.touch(exist_ok = True)
        refresh_cache = True

    log.info("Setting up database %r", str(metadbf))

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

        log.info("Loading folder %r into database", str(config.image_folder))

        for image in config.image_folder.glob("*.*"):
            if not image.is_file(): continue
            if image.name.startswith("."): continue
            _load_file(image, __db)

        __db.commit()
        with open(hashdbf, "wb") as hashdbfp:
            log.info("Writing to file...")
            __hashes.write_to_file(hashdbf)

    else:
        with open(hashdbf, "rb") as hashdbfp:
            log.info("Loading hashes from cache %r", str(hashdbf))
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)

        log.info("Catching up with image folder")
        uuids_in_folder = set()
        for image in config.image_folder.glob("*.*"):
            if not image.is_file(): continue
            if image.name.startswith("."): continue
            try:
                uuid = UUID(image.stem)
                uuids_in_folder.add(uuid)

            except: continue
        uuids_in_database = set(d[0] for d in __db.execute("select uid from Metadata").fetchall())
        for uid in uuids_in_database:
            _save_file(filename_for_uid(uid), __db)

        for uid in uuids_in_folder - uuids_in_database: # recently added
            _load_file(filename_for_uid(uid), __db)
        for uid in uuids_in_database - uuids_in_folder: # recently deleted
            _remove_image(uid, __db)

        __db.commit()
        

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
    class EventHandler(FileSystemEventHandler):
        def __init__(self):
            self._db = None

        @property
        def db(self):
            if self._db: return self._db
            self._db = connect_db(metadbf)
            return self._db

        #def on_any_event(self, event):
        #    log.info("%s %r", type(event), event.src_path)

        def on_moved(self, event):
            self.on_deleted({"src_path": event.src_path})
            self.on_created({"src_path": event.dest_path})

        def on_created(self, event):
            image = Path(event.src_path)
            if not image.is_file(): return
            if image.name.startswith("."): return 

            _load_file(image, self.db)
            self.db.commit()
        
        def on_deleted(self, event):
            image = Path(event.src_path)
            if not image.is_file(): return
            if image.name.startswith("."): return

            try:
                uid = UUID(image.stem)
            except: return # Not an image file

            _remove_image(uid, self.db)
            self.db.commit()

        def on_modified(self, event):
            image = Path(event.src_path)
            if not image.is_file(): return
            if image.name.startswith("."): return

            _save_file(image, self.db)
            self.db.commit()

    file_observer = Observer()
    file_observer.schedule(EventHandler(), str(config.image_folder.resolve()))
    file_observer.setDaemon(True)
    file_observer.start()

    try:
        while True: time.sleep(10) # Zzzzzzz....
    except KeyboardInterrupt:
        pass

def listen_for_db_changes(metadbf: Path):
    last_updated = datetime.utcfromtimestamp(os.path.getmtime(metadbf.resolve()))
    # We need our own connection since this is on a different thread
    db = connect_db(metadbf)
    try:
        while True:
            time.sleep(10)
            
            modified = db.execute("""
                select * from Metadata where last_updated > ?
            """, (last_updated,)).fetchall()
            last_updated = datetime.utcnow()

            for data in modified:
                filename = filename_for_uid(data["uid"])
                f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(filename))
                db_last_updated = data["last_updated"]
                if db_last_updated > f_last_updated:
                    meta = CuteMeta.from_file(filename)
                    log.info("Writing to file %r", str(filename))

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
                    # Make sure that the entry in the database stays the same as the file
                    epoch = time.mktime(db_last_updated.timetuple())
                    os.utime(str(filename), (epoch, epoch))
    except KeyboardInterrupt:
        pass
                

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
    return _get_meta(uid)

def _get_meta(uid: UUID):
    meta = CuteMeta(uid = uid, filename = filename_for_uid(uid))
    res = __db.execute("select * from Metadata where uid is ?", (str(uid.hex),)).fetchone()
    for name, v in zip(res.keys(), res):
        setattr(meta, name, v)
    return meta

@dbfun
def remove_image(uid: UUID):
    _remove_image(uid, __db)
    __db.commit()

def _remove_image(uid: UUID, db: sqlite3.Connection):
    log.info("Removing %s", uid)

    imghash = db.execute("""
        SELECT hash FROM Metadata WHERE uid = ?
    """, (uid,)).fetchone()["hash"]
    cnthash = db.execute("""
        SELECT count(uid) FROM Metadata where hash = ?
    """, (imghash,)).fetchone()[0]
    
    db.execute("DELETE FROM Metadata_Keywords WHERE uid = ?", (uid,))
    db.execute("DELETE FROM Metadata_Collections WHERE uid = ?", (uid,))
    db.execute("DELETE FROM Metadata WHERE uid = ?", (uid,))

    if cnthash == 1:
        __hashes.remove(imghash) # Only one hash by this name, it doesnt exist anymore now

@dbfun
def save_file(fp: Path):
    _save_file(fp, __db)
    __db.commit()

def _save_file(image: Path, db: sqlite3.Connection):
    f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(str(image)))
    uid = UUID(image.stem)
    data = db.execute("""
        select last_updated from Metadata where uid is ?
    """, (uid,)).fetchone()
    if f_last_updated > data["last_updated"]:
        log.info("Reading from file %r", str(image))
        meta = CuteMeta.from_file(image)
        _save_meta(meta, db, f_last_updated)

@dbfun
def save_meta(meta: CuteMeta):
    _save_meta(meta, __db, datetime.utcnow())
    __db.commit()

def _save_meta(meta: CuteMeta, db: sqlite3.Connection, timestamp):
    db.execute("""
        UPDATE Metadata SET
            last_updated = ?,
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
        timestamp,
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
def load_file(image):
    _load_file(image, __db)
    __db.commit()

def _load_file(image: Path, db: sqlite3.Connection):
    if image.name.startswith("."): return 

    f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(str(image)))
                
    log.debug("Loading %r", str(image))
    meta: CuteMeta = CuteMeta.from_file(image)
    if not meta.uid: return
    if not meta.hash: return

    try: __hashes.add(meta.hash)
    except KeyError: log.warn("Possible duplicate %r", str(image))

    db.execute(f"""
        INSERT INTO Metadata (
            uid, last_updated, hash, caption, author, source, group_id, rating, source_other, source_via
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )""", (
            meta.uid,
            f_last_updated,
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
        db.execute("""
            UPDATE Metadata SET date = ? WHERE uid is ?
        """, (meta.date, meta.uid))

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

@dbfun
def find_similar_images(uid, threshold, limit = 10):
    """ returns a list of uids for similar images for an image/uid """

    assert 0 <= threshold <= 1
    if limit > 100: limit = 100
    if limit < 1: limit = 1

    if isinstance(uid, str):
        uid = UUID(uid)

    meta = _get_meta(uid)
    hashes = __hashes.find_all_hamming_distance(meta.hash, floor(config.hash_length * (1 - threshold)), limit)

    if hashes:
        uids = __db.execute(f"select uid from Metadata where hash in ({','.join('?' for _ in range(len(hashes)))})", 
            tuple(format(h, 'x') for h in hashes))

        return [uid[0] for uid in uids]
    else:
        return []
