import sqlite3, atexit, re, json, sys, os, time
import logging

from datetime import datetime
from enum import Enum
from uuid import UUID
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent
from math import ceil
from threading import Thread, RLock
from contextlib import contextmanager
from functools import wraps

from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.meta import CuteMeta, Rating

import Pyro4
Pyro4.config.SERIALIZER = "pickle"
Pyro4.config.MAX_RETRIES = 1

# Type conversions
sqlite3.register_adapter(UUID, lambda uid: str(uid.hex))
sqlite3.register_converter("UUID", lambda v: UUID(hex = v.decode()))
sqlite3.register_adapter(Rating, lambda enum: enum.value)
sqlite3.register_converter("Rating", lambda v: Rating(v.decode()))
sqlite3.register_adapter(set, lambda s: json.dumps(list(s)))
sqlite3.register_converter("PSet", lambda v: set(json.loads(v.decode())))

log = logging.Logger("db")
log.addHandler(logging.StreamHandler(sys.stdout))

# Make sure only one thread talks to this

__hashes_lock = RLock()
__hashes: HashTree = None

@contextmanager
def get_hashes():
    with __hashes_lock:
        yield __hashes

__db: sqlite3.Connection = None
__rpccon = None

_functions = {}
def dbfun(fun):
    @wraps(fun)
    def wrapper(*args, db = None, **kwargs):
        global __rpccon
        if (__rpccon is None) and (not __hashes):
            try:
                __rpccon = Pyro4.Proxy(f"PYRO:cutespam-db@localhost:{config.service_port}")
                assert __rpccon.ping() == "pong"
            except Exception as e:
                print(str(e)) 
                __rpccon = False
                log.warn("No database service running, please consider starting it by running cutespam-db in a separate process or setting it up as a service with your system.")
                log.warn("Loading the database takes a long time but it makes the requests a lot faster.")
                init_db()
        
        if __rpccon:
            return getattr(__rpccon, fun.__name__)(*args, **kwargs)
        else:
            return fun(*args, db = db or __db, **kwargs)

    _functions[fun.__name__] = wrapper
    return wrapper

def regexp(expr, item):
    reg = re.compile(expr)
    return reg.search(item) is not None

def connect_db():
    db = sqlite3.connect(str(config.metadbf), detect_types = sqlite3.PARSE_DECLTYPES)
    db.create_function("REGEXP", 2, regexp)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    global __db, __hashes
    with __hashes_lock:

        log.info("Scanning database")

        refresh_cache = False
        if not config.metadbf.exists() or not config.hashdbf.exists():
            config.metadbf.touch(exist_ok = True)
            refresh_cache = True

        log.info("Setting up database %r", str(config.metadbf))

        __db = connect_db()
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
                keyword TEXT NOT NULL
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
            with open(config.hashdbf, "wb") as hashdbfp:
                log.info("Writing to file...")
                __hashes.write_to_file(config.hashdbf)

        else:
            with open(config.hashdbf, "rb") as hashdbfp:
                log.info("Loading hashes from cache %r", str(config.hashdbf))
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

        for uid in uuids_in_folder - uuids_in_database: # recently added
            _load_file(filename_for_uid(uid), __db)
        for uid in uuids_in_database - uuids_in_folder: # recently deleted
            _remove_image(uid, __db)

        for uid in uuids_in_database:
            try:
                _save_file(filename_for_uid(uid), __db)
            except FileNotFoundError: pass # was deleted earlier

        __db.commit()
            

        log.info("Done!")
        def exit():
            __db.commit()
            __db.close()

        atexit.register(exit)

def start_listeners():
    log.info("Listening for file changes")
    listen_for_file_changes()

    db_listener = Thread(target = listen_for_db_changes)
    db_listener.name = "Database change listener"
    db_listener.daemon = True
    db_listener.start()

def listen_for_file_changes():
    class EventHandler(FileSystemEventHandler):
        def __init__(self):
            self._db = None

        @property
        def db(self):
            if self._db: return self._db
            self._db = connect_db()
            return self._db

        #def on_any_event(self, event):
        #    log.info("%s %r", type(event), event.src_path)

        @staticmethod
        def is_image(file):
            if not file.is_file(): return False
            if file.name.startswith("."): return False
            try:
                UUID(file.stem)
                return True
            except: return False

        def on_moved(self, event):
            self.on_deleted(FileDeletedEvent(event.src_path))
            self.on_created(FileCreatedEvent(event.dest_path))

        def on_created(self, event):
            image = Path(event.src_path)
            if not self.is_image(image): return

            load_file(image, db = self.db)
        
        def on_deleted(self, event):
            image = Path(event.src_path)
            if image.name.startswith("."): return False
            try:
                uid = UUID(image.stem)
            except: return
            
            remove_image(uid, db = self.db)

        def on_modified(self, event):
            image = Path(event.src_path)
            if not self.is_image(image): return

            save_file(image, db = self.db)

    file_observer = Observer()
    file_observer.schedule(EventHandler(), str(config.image_folder.resolve()))
    file_observer.setDaemon(True)
    file_observer.start()

def listen_for_db_changes():
    last_updated = datetime.utcfromtimestamp(os.path.getmtime(config.metadbf.resolve()))
    # We need our own connection since this is on a different thread
    db = connect_db()
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
                    print("file:", f_last_updated, "database:", db_last_updated)

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
                
def filename_for_uid(uid) -> Path:
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
def query(keyword = None, not_keyword = None, author = None, limit = None, db: sqlite3.Connection = None):
    all_uids = get_all_uids(db = db)
    uids = set(all_uids)

    def select_keywords(keywords):
        return set(d[0] for d in db.execute(
            f"select uid from Metadata_Keywords where keyword in ({','.join('?' for k in keywords)})", 
            tuple(keywords)))

    if author is not None:
        uids &= set(d[0] for d in db.execute("select uid from Metadata where author is ?", (author or None,)))
    if keyword: 
        uids &= select_keywords(keyword)
    if not_keyword:
        uids &= all_uids - select_keywords(not_keyword)

    if limit and len(uids) > limit:
        return set(list(uids)[:limit])
    return uids

@dbfun
def get_tab_complete_uids(uidstr: str, db: sqlite3.Connection = None):
    uidstr = uidstr.replace("-", "")
    """ Returns a list of tab completions for a starting uid """
    uids = db.execute("select uid from Metadata where uid like ?", (uidstr + "%",)).fetchall()
    return set(uid[0] for uid in uids)

@dbfun
def get_all_uids(db: sqlite3.Connection = None):
    uids = db.execute("select uid from Metadata").fetchall()
    return set(uid[0] for uid in uids)

@dbfun
def get_meta(uid: UUID, db: sqlite3.Connection = None):
    meta = CuteMeta(uid = uid, filename = filename_for_uid(uid))
    uidstr = str(uid.hex)
    res = db.execute("select * from Metadata where uid is ?", (uidstr,)).fetchone()
    for name, v in zip(res.keys(), res):
        setattr(meta, name, v)

    keywords = db.execute("select keyword from Metadata_Keywords where uid is ?", (uidstr,)).fetchall()
    meta.keywords = set(k[0] for k in keywords)
    collections = db.execute("select collection from Metadata_Collections where uid is ?", (uidstr,)).fetchall()
    meta.collections = set(c[0] for c in collections)

    return meta

@dbfun
def remove_image(uid: UUID, db: sqlite3.Connection = None):
    _remove_image(uid, db)
    db.commit()

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
        with get_hashes() as hashes:
            try: hashes.remove(imghash) # Only one hash by this name, it doesnt exist anymore now
            except KeyError: pass

@dbfun
def save_file(fp: Path, db: sqlite3.Connection = None):
    _save_file(fp, db)
    db.commit()

def _save_file(image: Path, db: sqlite3.Connection):
    f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(str(image)))
    uid = UUID(image.stem)
    db_last_updated = db.execute("""
        select last_updated from Metadata where uid is ?
    """, (uid,)).fetchone()[0]
    
    if f_last_updated > db_last_updated:
        log.info("Reading from file %r", str(image))
        print("file:", f_last_updated, "database:", db_last_updated)
        meta = CuteMeta.from_file(image)
        _save_meta(meta, f_last_updated, db)
        db.commit()

@dbfun
def save_meta(meta: CuteMeta, db: sqlite3.Connection = None):
    _save_meta(meta, datetime.utcnow(), db)
    db.commit()

def _save_meta(meta: CuteMeta, timestamp, db: sqlite3.Connection):

    # Sync data

    db.execute("""
        DELETE FROM Metadata_Keywords WHERE uid is ?
    """, (meta.uid,))
    db.execute("""
        DELETE FROM Metadata_Collections WHERE uid is ?
    """, (meta.uid,))

    new_keywords = set(meta.keywords)
    if meta.author: 
        new_keywords.discard("missing:author")
    else: new_keywords.add("missing:author")
    if meta.caption:
        new_keywords.discard("missing:caption")
    else: new_keywords.add("missing:caption")
    if meta.source:
        new_keywords.discard("missing:source")
    else: new_keywords.add("missing:source")
    
    if new_keywords != meta.keywords:   # if we changed anything
        meta.keywords = new_keywords
        timestamp = datetime.utcnow()   # make sure we set the correct timestamp

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
    
    db.commit()

@dbfun
def load_file(image, db: sqlite3.Connection):
    _load_file(image, db)
    db.commit()

def _load_file(image: Path, db: sqlite3.Connection):
    if image.name.startswith("."): return 

    f_last_updated = datetime.utcfromtimestamp(os.path.getmtime(str(image)))
                
    log.debug("Loading %r", str(image))
    meta: CuteMeta = CuteMeta.from_file(image)
    if not meta.uid: return
    if not meta.hash: return

    try:
        with get_hashes() as hashes: 
            hashes.add(meta.hash)
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

def __collect_uids_with_hashes(hashes, db: sqlite3.Connection):
    ret = []
    if hashes:
        for similarity, h in hashes:
            similarity = 1 - (similarity / config.hash_length)
            res = db.execute("select uid from Metadata where hash is ?", (format(h, "x"),)).fetchall()
            for r in res:
                ret.append((similarity, r[0]))

    return sorted(ret, reverse = True)

@dbfun
def find_similar_images_hash(h: str, threshold: float, limit = 10, db: sqlite3.Connection = None):
    found = False
    distance = ceil(config.hash_length * (1 - threshold))

    hashes = []
    with get_hashes() as _hashes:
        # First see if the hash is inside there already
        if h in _hashes: 
            found = True
            hashes.append((0, int(h, 16)))
            
        else: _hashes.add(h) # Need to add it temporarily
        
        hashes += _hashes.find_all_hamming_distance(h, distance, limit)
        if not found: _hashes.remove(h)

    return __collect_uids_with_hashes(hashes, db)

@dbfun
def find_similar_images(uid: UUID, threshold: float, limit = 10, db: sqlite3.Connection = None):
    """ returns a list of uids for similar images for an image/uid """

    assert 0 <= threshold <= 1
    if limit > 100: limit = 100
    if limit < 1: limit = 1

    meta = get_meta(uid, db = db)
    distance = ceil(config.hash_length * (1 - threshold))
    with get_hashes() as _hashes:
        hashes = _hashes.find_all_hamming_distance(meta.hash, distance, limit)

    return __collect_uids_with_hashes(hashes, db)

@dbfun
def find_uids_with_hash(h: str, db: sqlite3.Connection = None):
    res = db.execute("select uid from Metadata where hash is ?", (h,))
    ret = set(r[0] for r in res)
    return ret

@dbfun
def find_all_duplicates(db: sqlite3.Connection = None):
    res = db.execute("select hash from Metadata group by hash having count(*) > 1")
    ret = []
    for h, in res:
        ret.append(find_uids_with_hash(h, db = db))
    return ret
