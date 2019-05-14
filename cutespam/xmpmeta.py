import json

from uuid import uuid4, UUID
from datetime import datetime
from textwrap import indent
from pathlib import Path
from enum import Enum

from cutespam import JSONEncoder

class Tag:
    def __init__(self, tag_name: str):
        self.name = tag_name
        self.type = None

    #def __set_name__(self, owner, name):
    #    self.type = typing.get_type_hints(owner)[name]

class Meta:
    _meta = None

    def __init__(self, meta = None, filename = None):
        self._meta = meta
        self._filename = filename or self._meta.filename
        for k, t in type(self).__dict__.items():
            if isinstance(t, Tag):
                setattr(self, k, None)

    def properties(self):
        for k, v in self.__dict__.items():
            if k in type(self).__dict__:
                yield (k, v)

    def to_string(self, fields = None):
        if fields and len(fields) == 1:
            return str(getattr(self, fields[0], ""))
        else:
            val = ""
            max_len = max(len(k) for (k, v) in self.properties() if not fields or k in fields)
            for k, v in self.properties():
                if not fields or k in fields:
                    lines = str(v).split("\n", 1)
                    val += "{0:>{indent}}: {1}\n".format(k, lines[0], indent = max_len)
                    if len(lines) > 1:
                        val += indent(lines[1], (max_len + 2) * " ") + "\n"
            return val[:-1]
    
    def to_json(self, fields = None):
        props = self.properties()
        if fields:  
            props = filter(lambda i: i[0] in fields, props)
        return json.dumps(dict(props), indent = 4, cls = JSONEncoder)

    def __str__(self):
        return self.to_string()

    def read_from_dict(self, d, ignore_missing_keys = False):
        for k, v in d.items():
            tag = getattr(type(self), k, None)
            if not tag and ignore_missing_keys:
                continue
            v = tag.type(v)
            setattr(self, k, v)

    def read(self):
        NotImplemented

    def write(self):
        NotImplemented

    def clear(self):
        if self._meta:
            self._meta.clear()
        for k, _ in self.properties():
            setattr(self, k, None)
            
    def release(self):
        NotImplemented # Probably not needed anymore

    @property
    def filename(self):
        return self._filename
    
    @classmethod
    def tag_names(cls):
        NotImplemented

    @classmethod
    def from_meta(cls, meta):
        NotImplemented # Is this even used anymore?

    @classmethod
    def from_file(cls, fp: Path):
        NotImplemented

class Rating(Enum):
    Safe = "s"
    Nudity = "n"
    Questionable = "q"
    Explicit = "e"

class CuteMeta(Meta):
    uid: UUID          # unique id for an image file
    hash: str          # image hash. 32 bit whash

    caption: str       # description
    author: str        # author
    keywords: set      # repeated, search keywords
    source: str        # primary source url, image file
    group_id: UUID     # group id, same as the uid of the first image in that group
    collections: set   # repeated, collections of images
    rating: Rating     # Rating of the image, ["s", "n", "q", "e"]
    
    date: datetime     # Timestamp of when the image was imported
    source_other: set  # list of urls where the image is published
    source_via: set    # list of urls related to the image

    def __init__(self, meta = None, filename = None, uid = None):
        self._db_uid = uid
        super().__init__(meta, filename)

    def add_characters(self, *characters):
        if not self.keywords:
            self.keywords = set()
        self.keywords |= set("character:" + k for k in characters)

    def generate_keywords(self):
        """ Syncs internal state. Returns True if changes have been made """

        new_keywords = set(self.keywords) if self.keywords else set()

        def missing(name, value):
            if value:
                new_keywords.discard("missing:" + name)
            else: new_keywords.add("missing:" + name)

        missing("author", self.author)
        missing("source", self.source)
        missing("caption", self.caption)
        missing("rating", self.rating)

        if self.collections:
            for collection in self.collections:
                new_keywords.add("collection:" + collection)
        
        if new_keywords != self.keywords:
            self.keywords = new_keywords
            return True
        
        return False

    @classmethod
    def from_db(cls, uid):
        from cutespam import db
        if isinstance(uid, str):
            uid = UUID(uid)
        return db.get_meta(uid)

    def write(self):
        from cutespam import db
        if self._db_uid:
            db.save_meta(self)
        else:
            super().write()