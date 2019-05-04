import sqlite3, atexit, re, json, sys, rpyc

from enum import Enum
from uuid import UUID
from threading import Thread
from pathlib import Path

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
                    "allow_public_attrs": True
                }).root
            except: 
                __rpccon = False
                log.warn("No database service running, please consider starting it by running cutespam-db in a separate process or setting it up as a service with your system.")
                log.warn("Loading the database takes a long time but it makes the requests a lot faster.")
                init_db()
        
        if __rpccon:
            return getattr(__rpccon, fun.__name__)(*args, **kwargs)
        else:
            return fun(*args, **kwargs)

    _functions[fun.__name__] = fun
    return wrapper

def regexp(expr, item):
    reg = re.compile(expr)
    return reg.search(item) is not None

def init_db():
    log.info("Scanning database")

    metadbf = config.cache_folder / "metadata.db"
    hashdbf = config.cache_folder / "hashes.db"

    refresh_cache = False
    if not metadbf.exists() or not hashdbf.exists():
        metadbf.touch(exist_ok = True)
        refresh_cache = True

    log.info('Setting up database "%s"', metadbf)

    global __db
    __db = sqlite3.connect(str(metadbf), detect_types = sqlite3.PARSE_DECLTYPES)
    __db.create_function("REGEXP", 2, regexp)
    __db.row_factory = sqlite3.Row
    __db.executescript(f"""
        CREATE TABLE IF not EXISTS Metadata (
            uid UUID PRIMARY KEY not null,
            last_updated DATETIME not null DEFAULT CURRENT_TIMESTAMP,
            hash TEXT not null,
            caption TEXT,
            author TEXT,
            source TEXT,
            group_id UUID,
            date DATETIME not null DEFAULT CURRENT_TIMESTAMP,
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

        log.info('Loading folder "%s" into database', config.image_folder)

        for image in config.image_folder.glob("*.*"):
            if not image.is_file(): continue
                
            log.debug('Loading "%s"', image)
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
            log.info('Loading hashes from cache "%s"', hashdbf)
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)

    log.info("Done!")
    db_listener = Thread(target = listen_for_db_changes, daemon = True)
    file_listener = Thread(target = listen_for_file_changes, daemon = True)
    db_listener.start()
    file_listener.start()

    def save_db():
        __db.commit()
        __db.close()

    atexit.register(save_db)
    
__last_updated = 0
def listen_for_file_changes():
    pass

def listen_for_db_changes():
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
    meta = CuteMeta(uid = uid, filename = filename_for_uid(uid))
    # uid, hash, caption, author, source, group_id, rating, source_other, source_via
    res = __db.execute("select * from Metadata where uid is ?", (str(uid.hex),)).fetchone()
    for name, v in zip(res.keys(), res):
        setattr(meta, name, v)
    return meta

@dbfun
def save_meta(meta: CuteMeta):
    pass

@dbfun
def notify_metadata_change(cute_meta: CuteMeta):
    pass

@dbfun
def find_similar_images(uid, threshold, limit = 10):
    """ returns a list of uids for similar images for an image/uid """
    if isinstance(uid, str):
        uid = UUID(str)
    
