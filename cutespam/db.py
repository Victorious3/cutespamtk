import sqlite3, atexit

from uuid import UUID
from xmlrpc.client import ServerProxy
from threading import Thread
from pathlib import Path

from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.meta import CuteMeta

import logging
log = logging.Logger("db")

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

def init_db():
    log.info("Scanning database")

    metadbf = config.cache_folder / "metadata.db"
    hashdbf = config.cache_folder / "hashes.db"

    refresh_cache = False
    if not metadbf.exists() or not hashdbf.exists():
        metadbf.touch(exist_ok = True)
        hashdbf.touch(exist_ok = True)
        refresh_cache = True

    log.info("Setting up database %s", metadbf)
    __db = sqlite3.connect(metadbf)
    __db.executescript(f"""
        CREATE TABLE IF not EXISTS Metadata (
            uid TEXT PRIMARY KEY CHECK (length(uid) == 32) not null,
            hash TEXT not null,
            caption TEXT,
            author TEXT,
            source TEXT,
            group_id TEXT CHECK (length(uid) == 32),
            date DATETIME not null,
            rating TEXT CHECK (rating in ('s', 'n', 'q', 'e'))
            source_other TEXT,
            source_via TEXT,
        ) WITHOUT ROWID;

        CREATE TABLE IF not EXISTS Metadata_Keywords (
            uid TEXT (length(uid) == 32) not null,
            keyword TEXT NOT NULL CHECK (tag REGEXP '{config.tag_regex}')
        );

        CREATE TABLE IF not EXISTS Metadata_Collections (
            uid TEXT (length(uid) == 32) not null,
            collection TEXT NOT NULL CHECK (tag REGEXP '{config.tag_regex}')
        );
    """)

    if refresh_cache:
        __hashes = HashTree(config.hash_length)

        for image in config.image_folder.glob("*.*"):
            meta: CuteMeta = CuteMeta.from_file(image)
            if not meta.uid: continue
            if not meta.hash: continue

            __hashes.add(meta.hash)
            
            __db.execute(f"""
                INSERT INTO Metadata (
                    uid, hash, caption, author, source, group_id, date, rating, source_other, source_via
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )""",
                meta.uid, meta.hash, meta.caption, meta.author, 
                meta.source, meta.group_id, meta.rating, meta.source_other, meta.source_via
            )

            if meta.keywords:
                __db.executemany(f"""
                   INSERT INTO Metadata_Keywords (
                       ?, ?
                   ) 	
                """, [(meta.uid, keyword) for keyword in meta.keywords])
            if meta.collections:
                __db.executemany(f"""
                   INSERT INTO Metadata_Collections (
                       ?, ?
                   ) 	
                """, [(meta.uid, collection) for collection in meta.collections])

        __db.commit()
        with open(hashdbf, "w") as hashdbfp:
            __hashes.write_to_file(hashdbf)

    else:
        with open(hashdbf, "r") as hashdbfp:
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)


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