import json, typing

from lxml import etree as ET
from uuid import uuid4, UUID
from datetime import datetime
from textwrap import indent
from pathlib import Path
from enum import Enum
from copy import deepcopy

from cutespam import JSONEncoder, BASE_PATH

RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

class Tag:
    def __init__(self, tag_name: str, tag_type: str, name:str, tpe: type):
        self.tag_name = tag_name
        self.tag_type = tag_type
        self.name = name
        self.type = tpe

class _Meta(type):
    def __init__(cls: "Meta", name, bases, nmspc):
        if cls._XMP:
            parser = ET.XMLParser(remove_blank_text = True)
            cls._XMP_ETREE = root = ET.parse(str(cls._XMP.resolve()), parser).getroot()

            for k, tpe in typing.get_type_hints(cls).items():
                if not k.startswith("_"):
                    # Figure out tag name for tag
                    elem = root.xpath(f"//*[@*='{{{k}}}']")
                    if elem: # Simple element
                        assert tpe not in (set, list), "Simple text element can't be a list or a set"
                        elem = elem[0]
                        tag_name = elem.xpath(f"name(@*[.='{{{k}}}'])")
                        prefix, suffix = tag_name.split(":")
                        tag_name = "{%s}" % elem.nsmap[prefix] + suffix
                        tag_type = None
                        del elem.attrib[tag_name]
                    else:
                        elem = root.xpath(f"//*[normalize-space()='{{{k}}}']")[-1].getparent()
                        tag_name = elem.tag
                        tag_type = elem[0].tag
                        elem.getparent().remove(elem)

                    setattr(cls, k, Tag(tag_name, tag_type, k, tpe))

class Meta(metaclass = _Meta):
    _XMP = None
    _XMP_ETREE: ET.Element = None

    def __init__(self, filename = None):
        self._filename = filename

        for k in self.tag_names():
            setattr(self, k, None)

    def properties(self):
        for k in self.tag_names():
            v = getattr(self, k)
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

            if v and not isinstance(tag, property) and not isinstance(v, tag.type):
                v = tag.type(v)
            setattr(self, k, v)

    def as_dict(self):
        return dict(self.properties())

    def read(self):
        def deserialize(value, tpe):
            if tpe is datetime:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
            return tpe(value)

        with open(self.filename, "r") as file:
            self._XMP_ETREE = root = ET.fromstring(file.read())
            
        for k in self.tag_names():
            value = None
            tag = getattr(type(self), k)

            if tag.tag_type:
                # complex value
                elem = root.find(f".//{tag.tag_name}")
                if elem is not None:
                    if tag.tag_type == "{%s}Alt" % RDF_NS:
                        value = elem[0][0].text
                        #if not value: value = None
                    else:
                        value = tag.type(v.text for v in elem[0])
                        #if len(value) == 1 and not list(value)[0]: value = None
            else:
                # simple value
                description = root.find(".//{%s}Description[@%s]" % (RDF_NS, tag.tag_name))
                if description is not None:
                    value = deserialize(description.attrib[tag.tag_name], tag.type)
                # maybe wrong format?
                elem = root.find(f".//{tag.tag_name}")
                if elem:
                    value = deserialize(elem.text, tag.type)
            
            setattr(self, k, value)

    def write(self):
        def serialize(value, tpe):
            if value is None: return None
            if issubclass(tpe, Enum):
                return value.value
            elif tpe is datetime:
                return value.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            return str(value)

        if self._XMP_ETREE is not None:
            self._XMP_ETREE = deepcopy(type(self)._XMP_ETREE)

        root = self._XMP_ETREE
        for k, value in self.properties():
            tag = getattr(type(self), k)
            elem = root.find(f".//{tag.tag_name}")
            description = root.find(".//{%s}Description" % RDF_NS)
            
            if elem:
                # delete existing value
                elem.getparent().remove(elem)

            if value is None: continue
            if tag.tag_type:
                # complex value
                if not value: continue # empty list/set
                propety = ET.Element(tag.tag_name)
                elem = ET.Element(tag.tag_type)
                if tag.tag_type == "{%s}Alt" % RDF_NS:
                    v = ET.Element("{%s}li" % RDF_NS)
                    v.attrib["{http://www.w3.org/XML/1998/namespace}lang"] = "x-default"
                    v.text = serialize(value, tag.type)
                    elem.append(v)
                else:
                    for e in value:
                        v = ET.Element("{%s}li" % RDF_NS)
                        v.text = e
                        elem.append(v)

                propety.append(elem)
                description.append(propety)
                
            else: # simple value
                description.attrib[tag.tag_name] = serialize(value, tag.type)
                    
        with open(self.filename, "w") as file:
            file.write(ET.tostring(self._XMP_ETREE, method = "xml", pretty_print = True).decode())

    def clear(self):
        for k, _ in self.properties():
            setattr(self, k, None)

    @property
    def filename(self):
        return self._filename
    
    @classmethod
    def tag_names(cls):
        names = []
        for k, t in vars(cls).items():
            if isinstance(t, Tag):
                names.append(k)
        return names

    @classmethod
    def from_file(cls, fp: Path):
        meta = cls(filename = fp)
        meta.read()
        return meta

class Rating(Enum):
    Safe = "s"
    Nudity = "n"
    Questionable = "q"
    Explicit = "e"

class CuteMeta(Meta):
    _XMP = BASE_PATH / "cute_meta.xmp"

    uid: UUID          # unique id for an image file
    hash: str          # image hash. 32 bit whash

    caption: str       # description
    authors: list      # author
    keywords: set      # repeated, search keywords
    source: str        # primary source url, image file
    group_id: UUID     # group id, same as the uid of the first image in that group
    collections: set   # repeated, collections of images
    rating: Rating     # Rating of the image, ["s", "n", "q", "e"]
    
    date: datetime     # Timestamp of when the image was imported
    last_updated: datetime # Timestamp of the last metadata change

    source_other: set  # list of urls where the image is published
    source_via: set    # list of urls related to the image

    @property
    def author(self):
        return self.authors[0] if self.authors else None

    @author.setter
    def author(self, value):
        if value is None: self.authors = None
        else: self.authors = [value]

    def __init__(self, filename = None, uid = None):
        self._db_uid = uid
        super().__init__(filename)

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
        
        if self.authors:
            for author in self.authors:
                new_keywords.add("author:" + author)
        
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