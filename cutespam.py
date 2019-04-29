#!/usr/bin/env python3

import subprocess
import argparse
import pyexiv2
import fileinput
import typing
import sys
import json
import codecs
import os

from uuid import uuid4, UUID
from typing import Set
from pathlib import Path
from glob import glob
from textwrap import indent
from datetime import datetime
from PIL import Image
from imagehash import phash
from functools import reduce
from io import BytesIO

xmp_namespace = "Cutespam"
xmp_namespace_url = "https://cute.spam/"

THUMBNAIL_SIZE = 256
THUMBNAIL_MIN_FSIZE = 100 * 1000

ARGS: argparse.Namespace

def partition(p, l):
    return reduce(lambda x, y: x[not p(y)].append(y) or x, l, ([], []))

def yn_choice(message, default='n'):
    choices = 'Y/n' if default.lower() in ('y', 'yes') else 'y/N'
    choice = input("%s (%s) " % (message, choices))
    values = ('y', 'yes', '') if choices == 'Y/n' else ('y', 'yes')
    return choice.strip().lower() in values

def print_path(fp):
    if ARGS.uri:
        print(Path(fp).absolute().as_uri())
    else:
        print(fp)
                
class _JSONEncoder(json.JSONEncoder):
    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, UUID):
            return str(obj)
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

    def __init__(self, meta):
        self._meta = meta
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
                if not isinstance(v, list):
                    v = [v]
                self._meta[tag.name] = tag.tag_type(tag.name, v)
            else:
                try: del self._meta[tag.name]
                except KeyError: pass

        self._meta.write()

    def clear(self):
        self._meta.clear()
        for k, _ in self.properties():
            setattr(self, k, None)
    
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
        try:
            UUID(hex = fp.stem)
        except ValueError:
            print("Warning: Malformed uuid in filename")

        meta = pyexiv2.ImageMetadata(str(fp))
        meta.read()
        return cls.from_meta(meta)

class CuteMeta(Meta):
    uid: UUID          = Tag("Iptc.Envelope.UNO")                  # unique id for an image file
    hash: str          = Tag("Iptc.Envelope.ProductId")            # image hash. 32 bit whash

    caption: str       = Tag("Iptc.Application2.Caption")          # description
    author: str        = Tag("Iptc.Application2.Credit")           # author
    keywords: set      = Tag("Iptc.Application2.Keywords")         # repeated, search keywords
    source: str        = Tag("Iptc.Application2.Source")           # primary source url, image file
    group_id: UUID     = Tag("Iptc.Application2.FixtureId")        # group id, same as the uid of the first image in that group
    collections: set   = Tag("Iptc.Application2.SuppCategory")     # repeated, collections of images
    rating: str        = Tag("Iptc.Application2.Urgency")          # Rating of the image, ["s", "n", "q", "e"] TODO: Validate
    
    date: datetime     = Tag("Xmp.dc.date")        # Timestamp of when the image was imported
    source_other: set  = Tag("Xmp.dc.publisher")   # list of urls where the image is published
    source_via: set    = Tag("Xmp.dc.relation")    # list of urls related to the image

    def add_characters(self, *characters):
        if not self.keywords:
            self.keywords = set()
        self.keywords |= set("character:" + k for k in characters)

def all_files_in_folders(folders):
    for folder in folders:
        for f in Path(folder).glob("*"):
            if f.name.startswith("."): continue
            if f.is_file(): yield f

def find_duplicates(files):
    ALL_HASHES = {}
    duplicates = []

    for f in files:
        try:
            meta = CuteMeta.from_file(f)
        except TypeError: continue

        h = meta.hash
        if h in ALL_HASHES.keys():
            hashes = ALL_HASHES[h]
            if len(hashes) == 1:
                duplicates.append(hashes)
            hashes.append(f)
        else:
            ALL_HASHES[h] = [f]

    return duplicates

def main():
    if ARGS.command == "probe":
        fp = Path(ARGS.file.name)
        cute_meta = CuteMeta.from_file(fp)
        if ARGS.json:
            print(cute_meta.to_json(ARGS.tag))
        else:
            print(cute_meta.to_string(ARGS.tag))
    elif ARGS.command == "filter":
        if ARGS.files:
            files = sum([glob(str(f)) for f in ARGS.files], [])
        elif not sys.stdin.isatty():
            files = [f.replace("\n", "") for f in fileinput.input('-')]
        else:
            files = glob("*.*")

        filtered = []
        for fp in files:
            try: cute_meta = CuteMeta.from_file(Path(fp))
            except (FileNotFoundError, TypeError): continue

            keywords = getattr(cute_meta, "keywords", set())
            if ARGS.tag and not set(ARGS.tag).issubset(keywords): continue
            if ARGS.not_tag and set(ARGS.not_tag).intersection(keywords): continue
            filtered.append(fp)
        for fp in filtered:
            print_path(fp)
    elif ARGS.command == "tag":
        fp = Path(ARGS.file.name)
        tag = ARGS.tag
        cute_meta = CuteMeta.from_file(fp)

        if ARGS.subcommand == "set":
            tpe = getattr(CuteMeta, tag).type
            val = ARGS.value
            # this was in the wrong order, oops
            if len(val) == 1:
                val = val[0]
            if issubclass(tpe, datetime):
                try:
                    val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    print("Invalid date format, use YY-MM-DD HH:MM:SS")
                    return

            curr_v = getattr(cute_meta, tag)   
            if curr_v and issubclass(tpe, (list, set)):
                if not yn_choice("You are about to overwrite multiple values, proceed?"): return

            setattr(cute_meta, tag, val)
        elif ARGS.subcommand == "delete":
            setattr(cute_meta, tag, None)
        elif ARGS.subcommand == "add":
            tpe = getattr(CuteMeta, tag).type
            if not issubclass(tpe, (list, set)):
                print("Can only add from list or set")
                return
            v = getattr(cute_meta, tag) or tpe()
            if tpe == list: v += ARGS.value
            else: v |= set(ARGS.value)

            setattr(cute_meta, tag, v)
        elif ARGS.subcommand == "remove":
            tpe = getattr(CuteMeta, tag).type
            if not issubclass(tpe, (list, set)):
                print("Can only remove to list or set")
                return
            v = getattr(cute_meta, tag) or set()
            v = set(v)
            v -= set(ARGS.value)
            setattr(cute_meta, tag, tpe(v))


        cute_meta.write()
    elif ARGS.command == "sync":
        fp = Path(ARGS.file.name)
        cute_meta = CuteMeta.from_file(fp)

        if ARGS.hash:
            with Image.open(fp) as img_data:
                cute_meta.hash = str(phash(img_data, hash_size=16))
            print("Generated hash", cute_meta.hash)
            cute_meta.write()
        if ARGS.uid:
            if cute_meta.uid:
                print("File already has a uid.")
            else:
                cute_meta.uid = uuid4()
                print("Created new uid:", cute_meta.uid)
            cute_meta.write()

            filename = fp.parent / (str(cute_meta.uid) + fp.suffix)
            if not filename.exists():
                os.rename(fp.resolve(), filename.resolve())
                print("Renamed file to match uid.")
        if ARGS.keywords:
            if cute_meta.keywords:
                keywords = cute_meta.keywords
            else:
                keywords = set()

            kw_collections, keywords = partition(lambda k: k.startswith("collection:"), keywords)
            kw_author, keywords = partition(lambda k: k.startswith("author:"), keywords)
            _, keywords = partition(lambda k: k.startswith("missing:"), keywords)
            kw_missing = set()

            kw_collections = set(c.split("collection:")[1] for c in kw_collections)
            if kw_collections:
                print("Using keyword collections")
                cute_meta.collections = kw_collections
            elif cute_meta.collections:
                print("Using internal collections")
                kw_collections = cute_meta.collections

            if len(kw_author) > 1:
                print("Multiple author tags, discarding")
            kw_author = kw_author.pop().split("author:")[1] if kw_author else None
            if kw_author:
                print("Using keyword author")
                cute_meta.author = kw_author
            elif cute_meta.author:
                print("Using internal author")
                kw_author = cute_meta.author

            if not cute_meta.author: 
                print("Missing author")
                kw_missing.add("author")
            if not cute_meta.caption: 
                print("Missing caption")
                kw_missing.add("caption")
            if not cute_meta.source: 
                print("Missing source")
                kw_missing.add("source")

            cute_meta.keywords = set(keywords) | set("missing:" + m for m in kw_missing) | set("collection:" + c for c in kw_collections)
            if kw_author: cute_meta.keywords.add("author:" + kw_author)
            cute_meta.write()
        if ARGS.clear_unknown:
            meta = cute_meta._meta
            known_tags = CuteMeta.known_exif_tags()
            before = len(meta)
            for key in meta.keys():
                if not key in known_tags:
                    del meta[key]
            meta.write()
            print("Removed", before - len(meta), "unknown tags.")
        if ARGS.thumbnail:
            fsize = os.path.getsize(fp.resolve())
            if fsize < THUMBNAIL_MIN_FSIZE:
                print("Image too small for thumbnail <100kb")
            else:
                meta = cute_meta._meta
                
                print("Generating preview image...")
                image = Image.open(fp)
                image.convert()
                write_tiff = image.mode == "RGBA"
                image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
                
                #from PIL import ImageDraw
                #draw = ImageDraw.Draw(image)
                #draw.text((0, 0), "SAMPLE SAMPLE SAMPLE", (0, 0, 0))

                buffer = BytesIO()
                if write_tiff:
                    image.save(buffer, format = "tiff")
                else:
                    image.save(buffer, format = "jpeg", quality = 100)
                image.close()
                
                meta.exif_thumbnail.data = buffer.getvalue()
                if write_tiff:
                    meta["Exif.Thumbnail.Compression"] = 1 # uncompressed
                    # TODO Exif tags do nothing on png
                
                meta.write()
                

if __name__ == "__main__":

    def unescaped_string(arg_str):
        return codecs.decode(str(arg_str), 'unicode_escape')

    parser = argparse.ArgumentParser(description='Cutespam cli')
    command = parser.add_subparsers(dest = "command")
    command.required = True

    c_all = argparse.ArgumentParser(add_help = False)
    c_all.add_argument("--uri", help = "Emits absolute file:// URIs intead of relative paths", action = "store_true")
    
    # TODO: action = "append"
    c_probe = command.add_parser("probe", parents = [c_all],
        help = "Outputs a file's tags")
    c_probe.add_argument("--tag", nargs = "+",
        help = "List of tags to include")
    c_probe.add_argument("--json", action = "store_true",
        help = "Output as json")
    c_probe.add_argument("file", type = argparse.FileType())

    # TAG
    c_tag = command.add_parser("tag", parents = [c_all])
    tag_subcommand = c_tag.add_subparsers(dest = "subcommand")

    c_set = tag_subcommand.add_parser("set", parents = [c_all],
        help = "Modify a file's tags")
    c_set.add_argument("tag",
        help = "Tag to set", choices = CuteMeta.tag_names())
    c_set.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to set. Multiple values for list or set")
    c_set.add_argument("file", type = argparse.FileType())

    c_add = tag_subcommand.add_parser("add", parents = [c_all],
        help = "Adds an additional value to a tag")
    c_add.add_argument("tag",
        help = "Tag to add to", choices = CuteMeta.tag_names())
    c_add.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to add")
    c_add.add_argument("file", type = argparse.FileType())

    c_remove = tag_subcommand.add_parser("remove", parents = [c_all],
        help = "Removes a value from a tag")
    c_remove.add_argument("tag",
        help = "Tag to remove from", choices = CuteMeta.tag_names())
    c_remove.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to remove")
    c_remove.add_argument("file", type = argparse.FileType())

    c_delete = tag_subcommand.add_parser("delete", parents = [c_all],
        help = "Deletes a tag completely")
    c_delete.add_argument("tag",
        help = "Tag to remove from", choices = CuteMeta.tag_names())
    c_delete.add_argument("file", type = argparse.FileType())

    # FILTER
    c_list = command.add_parser("filter", parents = [c_all],
        help = "Filters filenames for tags or properties")
    c_list.add_argument("--tag", nargs = "+", default = [], choices = CuteMeta.tag_names(),
        help = "Filters for tags")
    c_list.add_argument("--not-tag", nargs = "+", default = [],
        help = "Filters for missing tags")
    c_list.add_argument("files", nargs = "*",
        help = "Files to filter")

    # SYNC
    c_sync = command.add_parser("sync", parents = [c_all],
        help = "Fills missing metadata and syncs the internal state")
    c_sync.add_argument("--uid", action = "store_true",
        help = "Generates a new uid if missing and renames the file")
    c_sync.add_argument("--hash", action = "store_true",
        help = "Calculates the hash for this image")
    c_sync.add_argument("--keywords", action = "store_true",
        help = "Updates the keywords for author, missing and collection")
    c_sync.add_argument("--clear-unknown", action = "store_true",
        help = "Removes unwanted metadata")
    c_sync.add_argument("--thumbnail", action = "store_true",
        help = "Generates a thumbnail image to speed up folder actions")
    c_sync.add_argument("file", type = argparse.FileType())
    # TODO Add the stuff from import.py, autocompleting sources, metadatas and iqdb search

    ARGS = parser.parse_args()
    main()
