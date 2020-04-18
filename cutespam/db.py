import sqlite3, atexit, re, json, sys, os, time
import logging, queue

from datetime import datetime
from enum import Enum
from uuid import UUID
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent
from math import ceil, floor
from threading import Thread, RLock
from contextlib import contextmanager
from functools import wraps

from cutespam import log, OrderedSetQueue, OrderedSet
from cutespam.hashtree import HashTree
from cutespam.config import config
from cutespam.xmpmeta import CuteMeta, Rating

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

# Make sure only one thread talks to this

#__folder_lock = Lock() # TODO These can deadlock, figure out a better way of handling this
#__hashes_lock = Lock()
__lock = RLock() # This effectively makes everything single threaded
__hashes: HashTree = None

__db: sqlite3.Connection = None
__rpccon = None

def pyro_release():
    if __rpccon:
        __rpccon._pyroRelease() # Pyro likes to log to non existent loggers if I don't do that
atexit.register(pyro_release)

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
                log.error(str(e)) 
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

        for xmpf in config.image_folder.glob("*.xmp"):
            if not xmpf.is_file(): continue
            if xmpf.name.startswith("."): continue
            _load_file(xmpf, __db)

        __db.commit()
        with open(config.hashdbf, "wb") as hashdbfp, __lock:
            log.info("Writing hashes to file...")
            __hashes.write_to_file(hashdbfp)

    else:
        with open(config.hashdbf, "rb") as hashdbfp, __lock:
            log.info("Loading hashes from cache %r", str(config.hashdbf))
            __hashes = HashTree.read_from_file(hashdbfp, config.hash_length)

    log.info("Catching up with image folder")
    uuids_in_folder = set()
    for xmpf in config.image_folder.glob("*.xmp"):
        if not xmpf.is_file(): continue
        if xmpf.name.startswith("."): continue

        try:
            uuid = UUID(xmpf.stem)
            uuids_in_folder.add(uuid)

        except: continue
    uuids_in_database = set(d[0] for d in __db.execute("select uid from Metadata").fetchall())

    for uid in uuids_in_folder - uuids_in_database: # recently added
        _load_file(xmp_file_for_uid(uid), __db)
    for uid in uuids_in_database - uuids_in_folder: # recently deleted
        _remove_image(uid, __db)

    for uid in uuids_in_database:
        try:
            _save_file(xmp_file_for_uid(uid), __db)
        except FileNotFoundError: pass # was deleted earlier

    __db.commit()
        

    log.info("Done!")
    def exit():
        log.info("Closing database connection")
        __db.commit()
        __db.close()

        with open(config.hashdbf, "wb") as hashdbfp, __lock:
            log.info("Writing hashes to file...")
            __hashes.write_to_file(hashdbfp)
        
        log.info("Done!")

    atexit.register(exit)

def start_listeners():
    log.info("Listening for file changes")
    listen_for_file_changes()

    db_listener = Thread(target = listen_for_db_changes)
    db_listener.name = "Database change listener"
    db_listener.daemon = True
    db_listener.start()

def listen_for_file_changes():
    event_queue = OrderedSetQueue()

    def retry(action, event): # TODO Untested
        try: action()
        except:
            log.warn("Event %s failed, adding to backlog", event)
            event_queue.put(event)

    def poll_failed():
        while True:
            while not event_queue.empty():
                event = event_queue.get_nowait()
                emitter.queue_event(event)
                event_queue.task_done()
            time.sleep(2)
        
    failed_retry = Thread(target = poll_failed)
    failed_retry.name = "Thread to retry failed filesystem events"
    failed_retry.daemon = True
    failed_retry.start()

    class EventHandler(FileSystemEventHandler):
        def __init__(self):
            self._db = None

        @property
        def db(self):
            if self._db: return self._db
            self._db = connect_db()
            return self._db

        def on_any_event(self, event):
            if config.trace_debug:
                log.debug("%s %r %r", type(event), getattr(event, "src_path", None), getattr(event, "dest_path", None))

        @staticmethod
        def is_xmp_file(file: Path, is_file = True):
            if is_file and not file.is_file(): return False
            if file.suffix != ".xmp": return False
            if file.name.startswith("."): return False
            try:
                UUID(file.stem)
                return True
            except: return False

        def on_moved(self, event):
            self.on_deleted(FileDeletedEvent(event.src_path))
            self.on_created(FileCreatedEvent(event.dest_path))

        def on_created(self, event):
            file = Path(event.src_path)
            if not self.is_xmp_file(file): return

            retry(lambda: load_file(file, db = self.db), event)
        
        def on_deleted(self, event):
            file = Path(event.src_path)
            if not self.is_xmp_file(file, is_file = False): return

            try:
                uid = UUID(file.stem)
            except: return
            retry(lambda: remove_image(uid, db = self.db), event)

        def on_modified(self, event):
            file = Path(event.src_path)
            if not self.is_xmp_file(file): return

            retry(lambda: save_file(file, db = self.db), event)

    file_observer = Observer()
    watch = file_observer.schedule(EventHandler(), str(config.image_folder.resolve()))
    emitter = file_observer._emitter_for_watch.get(watch)
    file_observer.setDaemon(True)
    file_observer.start()

def listen_for_db_changes():
    last_updated = datetime.utcfromtimestamp(os.path.getmtime(config.metadbf.resolve()))
    # We need our own connection since this is on a different thread
    db = connect_db()
    while True:
        time.sleep(10)
        
        modified = db.execute("""
            select * from Metadata where last_updated > ?
        """, (last_updated,)).fetchall()
        last_updated = datetime.utcnow()

        for data in modified:
            with __lock:
                filename = xmp_file_for_uid(data["uid"])
                meta = CuteMeta.from_file(filename)

                f_last_updated = meta.last_updated
                db_last_updated = data["last_updated"]
                if db_last_updated > f_last_updated:
                    log.info("Writing to file %r", str(filename))
                    log.debug("file: %s database: %s", f_last_updated, db_last_updated)

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
                    meta.last_updated = db_last_updated # Make sure that the entry in the database stays the same as the file
                    meta.write()

def xmp_file_for_uid(uid) -> Path:
    if isinstance(uid, str):
        uid = UUID(str)
    
    filename = (config.image_folder / str(uid)).with_suffix(".xmp")
    if filename.exists(): return filename

    raise FileNotFoundError("No file for uuid %s found", uid)
                
def picture_file_for_uid(uid) -> Path:
    if isinstance(uid, str):
        uid = UUID(uid)

    filename = config.image_folder / str(uid)
    for ext in config.extensions:
        filename = filename.with_suffix(ext)
        if filename.exists(): return filename
    
    raise FileNotFoundError("No file for uuid %s found", uid)

@dbfun
def query(
    keyword = None, not_keyword = None,
    author = None, caption = None, source = None,
    rating = None,
    limit = None, random = False,
    db: sqlite3.Connection = None, **kwargs) -> list:

    all_uids = OrderedSet(get_all_uids(db = db, random = random))
    uids = OrderedSet(all_uids)

    def select_keywords(keywords):
        return set(d[0] for d in db.execute(
            f"select uid from Metadata_Keywords where keyword in ({','.join('?' for k in keywords)})", 
            tuple(keywords)))

    def select_single(name, value):
        return set(d[0] for d in db.execute(
            f"select uid from Metadata where {name} {'is' if value == '' else 'like'} ?", (value or None,)
        ))

    if author is not None:
        uids &= select_single("author", author)
    if caption is not None:
        uids &= select_single("caption", caption)
    if source is not None:
        uids &= select_single("source", source)
    if rating is not None:
        uids &= select_single("rating", rating)

    if keyword: 
        uids &= select_keywords(keyword)
    if not_keyword:
        uids &= all_uids - select_keywords(not_keyword)

    if limit and len(uids) > limit:
        return list(uids)[:limit]
    return list(uids)

@dbfun
def get_tab_complete_keywords(keywordstr: str = None, db: sqlite3.Connection = None) -> set:
    keywords = db.execute("select distinct keyword from Metadata_Keywords where keyword like ? order by keyword", ((keywordstr if keywordstr else "") + "%",)).fetchall()
    return set(keyword[0] for keyword in keywords)

@dbfun
def get_uids_from_keyword(keyword: str, db: sqlite3.Connection = None) -> set:
    uids = db.execute("select uid from Metadata_Keywords where keyword like ? order by keyword", (keyword,)).fetchall()
    return set(uid[0] for uid in uids)

@dbfun
def get_uids_from_keyword_list(keywords, db: sqlite3.Connection = None) -> set:
    ret_uids = set(get_all_uids(db = db))
    for keyword in keywords:
        uids = get_uids_from_keyword(keyword, db = db)
        ret_uids &= uids

    return ret_uids

@dbfun
def get_tab_complete_uids(uidstr: str, db: sqlite3.Connection = None) -> set:
    """ Returns a list of tab completions for a starting uid """

    uidstr = uidstr.replace("-", "")
    uids = db.execute("select uid from Metadata where uid like ?", (uidstr + "%",)).fetchall()
    return set(uid[0] for uid in uids)

@dbfun
def get_random_uid(db: sqlite3.Connection = None):
    uid = db.execute("select uid from Metadata order by random() limit 1").fetchone()[0]
    return uid

@dbfun
def get_all_uids(db: sqlite3.Connection = None, random = False) -> list:
    uids = db.execute("select uid from Metadata" + (" order by random()" if random else "")).fetchall()
    return list(uid[0] for uid in uids)

@dbfun
def get_meta(uid: UUID, db: sqlite3.Connection = None):
    meta = CuteMeta(uid = uid, filename = xmp_file_for_uid(uid))
    uidstr = str(uid.hex)
    res = db.execute("select * from Metadata where uid is ?", (uidstr,)).fetchone()
    for name, v in zip(res.keys(), res):
        setattr(meta, name, v)

    keywords = db.execute("select keyword from Metadata_Keywords where uid is ?", (uidstr,)).fetchall()
    meta.keywords = set(k[0] for k in keywords) if keywords else None
    collections = db.execute("select collection from Metadata_Collections where uid is ?", (uidstr,)).fetchall()
    meta.collections = set(c[0] for c in collections) if collections else None

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
        with __lock:
            try: __hashes.remove(imghash) # Only one hash by this name, it doesnt exist anymore now
            except KeyError: pass

@dbfun
def save_file(fp: Path, db: sqlite3.Connection = None):
    _save_file(fp, db)
    db.commit()

def _save_file(xmpf: Path, db: sqlite3.Connection):
    with __lock:
        meta = CuteMeta.from_file(xmpf)
        f_last_updated = meta.last_updated
        uid = UUID(xmpf.stem)
        db_last_updated = db.execute("""
            select last_updated from Metadata where uid is ?
        """, (uid,)).fetchone()[0]
        
        if f_last_updated > db_last_updated:
            log.info("Reading from file %r", str(xmpf))
            log.debug("file: %s database: %s", f_last_updated, db_last_updated)
            _save_meta(meta, f_last_updated, db)
            db.commit()

@dbfun
def save_meta(meta: CuteMeta, db: sqlite3.Connection = None):
    _save_meta(meta, datetime.utcnow(), db)
    db.commit()

def _save_meta(meta: CuteMeta, timestamp: datetime, db: sqlite3.Connection):

    # Sync data
    if meta.generate_keywords():
        log.info("Updated autogenerated keywords")
        timestamp = datetime.utcnow() # make sure we set the correct timestamp

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

@dbfun
def load_file(xmpf, db: sqlite3.Connection):
    _load_file(xmpf, db)
    db.commit()

def _load_file(xmpf: Path, db: sqlite3.Connection):
    meta: CuteMeta = CuteMeta.from_file(xmpf)
    timestamp = meta.last_updated

    if not meta.uid: return
    if not meta.hash: return

    log.info("Loading %r", str(xmpf))

    # Sync data
    if meta.generate_keywords():
        log.info("Updated autogenerated keywords")
        timestamp = datetime.utcnow() # make sure we set the correct timestamp 

    with __lock:
        try: __hashes.add(meta.hash)
        except KeyError: log.warn("Possible duplicate %r", str(xmpf))

    db.execute(f"""
        INSERT INTO Metadata (
            last_updated, uid, hash, caption, author, source, group_id, rating, source_other, source_via
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )""", (
            timestamp,
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

    assert 0 <= threshold <= 1
    if limit > 100: limit = 100
    if limit < 1: limit = 1

    found = False
    distance = ceil(config.hash_length * (1 - threshold))

    hashes = []
    with __lock:
        # First see if the hash is inside there already
        if h in __hashes: 
            found = True
            hashes.append((0, int(h, 16)))
            
        else: __hashes.add(h) # Need to add it temporarily
        
        hashes += __hashes.find_all_hamming_distance(h, distance, limit)
        if not found: __hashes.remove(h)

    return __collect_uids_with_hashes(hashes, db)

@dbfun
def find_similar_images(uid: UUID, threshold: float, limit = 10, db: sqlite3.Connection = None):
    """ returns a list of uids for similar images for an image/uid """

    assert 0 <= threshold <= 1
    if limit > 100: limit = 100
    if limit < 1: limit = 1

    meta = get_meta(uid, db = db)
    distance = ceil(config.hash_length * (1 - threshold))
    with __lock:
        hashes = __hashes.find_all_hamming_distance(meta.hash, distance, limit)

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
