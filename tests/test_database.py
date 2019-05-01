import pytest

from cutespam.hashtree import HashTree
from cutespam.meta import CuteMeta

from pathlib import Path

HASH_FILE = Path("tests/data/hashes.txt")
DATABASE_FILE = Path("tests/data/database.db")

def test_write_database(data_folder):
    Path("tests/data/").mkdir(exist_ok = True) 

    tree = HashTree(256)

    if not data_folder: 
        # reading hashes from the file
        with open(HASH_FILE, "r") as hashesf:
            hashes = hashesf.readlines()
            tree |= hashes

    else:
        # reading hashes from the image files in the specified location
        with open(HASH_FILE, "w") as hashesf:
            for image in data_folder.glob("*.*"):
                meta = CuteMeta.from_file(image)
                try: tree.add(meta.hash)
                except KeyError: continue
                hashesf.write(str(meta.hash) + "\n")
                    
    # serialize tree
    with open(DATABASE_FILE, "wb") as database:
        tree.write_to_file(database)

def test_read_database():
    databasef = Path(DATABASE_FILE)

    with open(databasef, "rb") as database:
        tree = HashTree.read_from_file(database, 256)

    with open(HASH_FILE, "r") as hashesf:
        for h in hashesf:
            assert h in tree