import argparse
from cutespam.cli import UUIDCompleter

DESCRIPTION = "Imports an image file. Uses IQDB to fetch metadata"

def main(ARGS):
    import shutil, time, sys
    from PIL import Image
    from uuid import UUID, uuid4
    from datetime import datetime
    from pathlib import Path

    import cutespam.db
    from cutespam import yn_choice
    from cutespam.api import read_meta_from_dict
    from cutespam.hash import hash_meta
    from cutespam.iqdb import iqdb, upscale
    from cutespam.meta import CuteMeta
    from cutespam.config import config
    from cutespam.db import find_similar_images_hash, filename_for_uid
    
    file = Path(ARGS.file)
    
    with Image.open(file) as imgf:
        width, height = imgf.size
        resolution = width * height

    print(f"Resolution: {width}x{height}")
    print("Fetching iqdb results")
    with open(file, "rb") as fp:
        result = iqdb(file = fp, threshold = 0.9)
    
    source, data, service = upscale(result, resolution)
    if not source:
        if not yn_choice("No relevant images found. Add anyways?"): return
    else: print("Found image on", service)
    
    meta = CuteMeta.from_file(file)
    meta.uid = uuid4()
    meta.source = source
    meta.date = datetime.utcnow()

    hash_meta(meta)

    if data:
        read_meta_from_dict(meta, data)
    
    meta.generate_keywords()

    print("Metadata:")
    print(meta)

    similar = find_similar_images_hash(meta.hash, 0.9)
    if similar:
        print()
        print("Found potential duplicates:")
        for s in similar:
            print(f"{s[0]:.1%}: {filename_for_uid(s[1]).resolve().as_uri() if ARGS.uri else s[1]}")
        if not yn_choice("Proceed?"): return
    
    meta.write()
    meta.release()

    print("Done")
    f = shutil.move if ARGS.move else shutil.copy
    f(str(file), str(config.image_folder / (str(meta.uid) + file.suffix)))
    

def args(parser):
    parser.add_argument("file")
    parser.add_argument("--uri", action = "store_true")
    parser.add_argument("--move", action = "store_true",
        help = "If set to true, the file will be moved instead of copied")
