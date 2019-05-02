import argparse
import os

from pathlib import Path
from datetime import datetime
from PIL import Image
from io import BytesIO

from cutespam import partition
from cutespam.config import config
from cutespam.meta import CuteMeta
from cutespam.hash import hash_img

from imagehash import phash
from uuid import uuid4, UUID

DESCRIPTION = "Fills missing metadata and syncs the internal state"

def main(ARGS):
    fp = Path(ARGS.file.name)
    cute_meta = CuteMeta.from_file(fp)

    if ARGS.hash:
        hash_img(cute_meta)
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
        if fsize < config.thumbnail_min_filesize * 1000:
            print("Image too small for thumbnail <100kb")
        else:
            meta = cute_meta._meta
            
            print("Generating preview image...")
            image = Image.open(fp)
            image.convert()
            write_tiff = image.mode == "RGBA"
            image.thumbnail((config.thumbnail_size, config.thumbnail_size))
            
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

def args(parser):
    parser.add_argument("--uid", action = "store_true",
        help = "Generates a new uid if missing and renames the file")
    parser.add_argument("--hash", action = "store_true",
        help = "Calculates the hash for this image")
    parser.add_argument("--keywords", action = "store_true",
        help = "Updates the keywords for author, missing and collection")
    parser.add_argument("--clear-unknown", action = "store_true",
        help = "Removes unwanted metadata")
    parser.add_argument("--thumbnail", action = "store_true",
        help = "Generates a thumbnail image to speed up folder actions")
    parser.add_argument("file", type = argparse.FileType())