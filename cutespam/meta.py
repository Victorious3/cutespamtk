import json
import pyexiv2
import typing

from uuid import uuid4, UUID
from datetime import datetime
from textwrap import indent
from pathlib import Path
from enum import Enum

class _JSONEncoder(json.JSONEncoder):
    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, (UUID, datetime)):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        return json.JSONEncoder.default(self, obj)


class Tag:
    def __init__(self, tag_name: str):
        self.name = tag_name
        self.type = None
        if tag_name.startswith("Iptc."):
            self.tag_type = pyexiv2.IptcTag
        elif tag_name.startswith("Exif."):
            self.tag_type = pyexiv2.ExifTag
        elif tag_name.startswith("Xmp."):
            self.tag_type = pyexiv2.XmpTag
        else: raise ValueError("Invalid Tag name")

    def __set_name__(self, owner, name):
        self.type = typing.get_type_hints(owner)[name]

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
        return json.dumps(dict(props), indent = 4, cls = _JSONEncoder)

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
        self._meta.read()
        for k, _ in self.properties():
            tag = getattr(type(self), k)
            if tag.name in self._meta:
                val = self._meta[tag.name].value
                if not issubclass(tag.type, (list, set)):
                    val = val[0]
                if not issubclass(tag.type, datetime):
                    val = tag.type(val)
                setattr(self, k, val)

    def write(self):
        for k, v in self.properties():
            tag = getattr(type(self), k)
            if v:
                if isinstance(v, UUID):
                    v = str(v.hex) # TODO factor out
                elif isinstance(v, set):
                    v = list(v)
                elif isinstance(v, Enum):
                    v = v.value
                if not isinstance(v, list):
                    v = [v]
                self._meta[tag.name] = tag.tag_type(tag.name, v)
            else:
                try: del self._meta[tag.name]
                except KeyError: pass

        self._meta.write()

    def clear(self):
        if self._meta:
            self._meta.clear()
        for k, _ in self.properties():
            setattr(self, k, None)

    @property
    def filename(self):
        return self._filename
    
    @classmethod
    def tag_names(cls):
        tags = [k for (k, t) in cls.__dict__.items() if isinstance(t, Tag)]
        return tags

    @classmethod
    def known_exif_tags(cls):
        tag_names = [t.name for (k, t) in cls.__dict__.items() if isinstance(t, Tag)]
        return set(tag_names)

    @classmethod
    def from_meta(cls, meta):
        cm = cls(meta)
        cm.read()
        return cm

    @classmethod
    def from_file(cls, fp: Path):
        #try:
        #    UUID(hex = fp.stem)
        #except ValueError:
        #    print("Warning: Malformed uuid in filename")

        meta = pyexiv2.ImageMetadata(str(fp))
        meta.read()
        return cls.from_meta(meta)

class Rating(Enum):
    Safe = "s"
    Nudity = "n"
    Questionable = "q"
    Explicit = "e"

class CuteMeta(Meta):
    uid: UUID          = Tag("Iptc.Envelope.UNO")                  # unique id for an image file
    hash: str          = Tag("Iptc.Envelope.ProductId")            # image hash. 32 bit whash

    caption: str       = Tag("Iptc.Application2.Caption")          # description
    author: str        = Tag("Iptc.Application2.Credit")           # author
    keywords: set      = Tag("Iptc.Application2.Keywords")         # repeated, search keywords
    source: str        = Tag("Iptc.Application2.Source")           # primary source url, image file
    group_id: UUID     = Tag("Iptc.Application2.FixtureId")        # group id, same as the uid of the first image in that group
    collections: set   = Tag("Iptc.Application2.SuppCategory")     # repeated, collections of images
    rating: Rating     = Tag("Iptc.Application2.Urgency")          # Rating of the image, ["s", "n", "q", "e"] TODO: Validate
    
    date: datetime     = Tag("Xmp.dc.date")        # Timestamp of when the image was imported
    source_other: set  = Tag("Xmp.dc.publisher")   # list of urls where the image is published
    source_via: set    = Tag("Xmp.dc.relation")    # list of urls related to the image

    def __init__(self, meta = None, filename = None, uid = None):
        self._db_uid = uid
        super().__init__(meta, filename)

    def add_characters(self, *characters):
        if not self.keywords:
            self.keywords = set()
        self.keywords |= set("character:" + k for k in characters)

    @classmethod
    def from_db(cls, uid):
        if isinstance(uid, str):
            uid = UUID(uid)
        return db.get_meta(uid)

    def write(self):
        if self._db_uid:
            db.save_meta(self)
        else:
            super().write()


from cutespam import db # Circualar dependency