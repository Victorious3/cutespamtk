import argparse
from cutespam.cli import UUIDCompleter

DESCRIPTION = "Imports an image file. Uses IQDB to fetch metadata"

def main(ARGS):
    import shutil, time, sys
    from PIL import Image
    from uuid import uuid4
    from datetime import datetime
    from pathlib import Path

    from cutespam import yn_choice
    from cutespam.api import read_meta_from_dict, get_cached_file
    from cutespam.iqdb import iqdb, upscale
    from cutespam.hash import hash_img
    from cutespam.xmpmeta import CuteMeta
    from cutespam.config import config
    from cutespam.db import find_similar_images_hash, picture_file_for_uid

    if ARGS.file and ARGS.file[0] == "-" and not sys.stdin.isatty():
        ARGS.file = sys.stdin.read().splitlines()

    for file in ARGS.file:
        file = Path(file)
        if file.suffix == ".xmp": continue
        xmpfile = file.with_suffix(".xmp")

        meta = CuteMeta(filename = xmpfile)
        meta.hash = hash_img(file)

        similar = find_similar_images_hash(meta.hash, 0.9)
        if similar:
            print()
            print("Found potential duplicates:")
            for s in similar:
                print(f"{s[0]:.1%}: {picture_file_for_uid(s[1]).resolve().as_uri() if ARGS.uri else s[1]}")
            if not ARGS.add_duplicate and (ARGS.skip_duplicate or not yn_choice("Proceed?")): continue

        with Image.open(file) as imgf:
            width, height = imgf.size
            resolution = width * height

        print(f"Resolution: {width}x{height}")
        print("Fetching iqdb results")
        with open(file, "rb") as fp:
            result = iqdb(file = fp, threshold = 0.9)
        
        source, data, service, r_resolution = upscale(result, resolution)
        if not source:
            if not ARGS.add_no_iqdb and (ARGS.skip_no_iqdb or not yn_choice("No relevant images found. Add anyways?")): continue
        else: print("Found image on", service)
        
        if r_resolution > resolution:
            file = get_cached_file(source)
        
        
        meta.uid = uuid4()
        meta.source = source
        meta.date = datetime.utcnow()

        if data:
            read_meta_from_dict(meta, data)
        
        meta.generate_keywords()

        print("Metadata:")
        print(meta)

        meta.last_updated = datetime.utcnow()
        meta.write()

        print("Done")
        f = shutil.move if ARGS.move else shutil.copy
        f(str(file), str(config.image_folder / (str(meta.uid) + file.suffix)))
        f(str(xmpfile), str(config.image_folder / (str(meta.uid) + ".xmp")))
        

def args(parser):
    parser.add_argument("--uri", action = "store_true")
    parser.add_argument("--skip-duplicate", action = "store_true",
        help = "Skips duplicates instead of asking")
    parser.add_argument("--add-duplicate", action = "store_true",
        help = "Adds duplicates instead of asking")   
    parser.add_argument("--skip-no-iqdb", action = "store_true",
        help = "Skips an image if no iqdb result was found")
    parser.add_argument("--add-no-iqdb", action = "store_true",
        help = "Adds an image if no iqdb result was found")
    parser.add_argument("-m", "--move", action = "store_true",
        help = "If set to true, the file will be moved instead of copied")

    parser.add_argument("file", nargs = "+")
