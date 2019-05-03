import sqlite3, atexit, re, json, sys

from enum import Enum
from uuid import UUID
from xmlrpc.client import ServerProxy
from threading import Thread
from pathlib import Path

from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.meta import CuteMeta, Rating

import logging

sqlite3.register_adapter(UUID, lambda uid: str(uid.hex))
sqlite3.register_converter("UUID", lambda v: UUID(v))
sqlite3.register_adapter(Rating, lambda enum: enum.value)
sqlite3.register_converter("Rating", lambda v: Rating(v))
sqlite3.register_adapter(set, lambda s: json.dumps(list(s)))
sqlite3.register_converter("PSet", lambda v: set(json.loads(v)))

log = logging.Logger("db")
log.addHandler(logging.StreamHandler(sys.stdout))

__hashes: HashTree
__db: sqlite3.Connection

__rpccon: ServerProxy
_functions = []
def dbfun(fun):
    def wrapper(*args, **kwargs):
        global __rpccon
        if __rpccon is None:
            try: __rpccon = ServerProxy(f"http://localhost:{config.service_port}/", use_builtin_types = True)
            except: 
                __rpccon = False
                init_db()
        
        if __rpccon:
            return getattr(__rpccon, fun.__name__)(*args, **kwargs)
        else:
            return fun(*args, **kwargs)

    _functions.append(fun)
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

    log.info("Setting up database %s", metadbf)
    __db = sqlite3.connect(str(metadbf))
    __db.create_function("REGEXP", 2, regexp)
    __db.executescript(f"""
        CREATE TABLE IF not EXISTS Metadata (
            uid UUID PRIMARY KEY not null,
            hash TEXT not null,
            caption TEXT,
            author TEXT,
            source TEXT,
            group_id UUID,
            date DATETIME DEFAULT CURRENT_TIMESTAMP,
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
                    uid, hash, caption, author, source, group_id, date, rating, source_other, source_via
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""", (
                    meta.uid, 
                    meta.hash, 
                    meta.caption, 
                    meta.author,
                    meta.source, 
                    meta.group_id,
                    meta.date, 
                    meta.rating, 
                    meta.source_other, 
                    meta.source_via
                )
            )

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
        with open(hashdbf, "w") as hashdbfp:
            log.info("Writing to file...")
            __hashes.write_to_file(hashdbf)

    else:
        with open(hashdbf, "r") as hashdbfp:
            log.info('Loading hashes from cached file "%s"', hashdbf)
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)

    log.info("Done!")
    listener = Thread(target = listen_for_file_changes, daemon = True)
    listener.start()

    def save_db():
        __db.commit()
        __db.close()

    atexit.register(save_db)
    
__last_updated = 0
def listen_for_file_changes():
    pass

def sync_metadata(cute_meta):
    pass

@dbfun
def find_similar_images(uid, threshold, limit = 10):
    """ returns a list of uids for similar images for an image/uid """