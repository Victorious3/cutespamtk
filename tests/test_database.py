import pytest

from cutespam.hashtree import HashTree
from cutespam.meta import CuteMeta

from pathlib import Path

def test_write_database(data_folder):
    Path("tests/data/").mkdir(exist_ok = True) 

    tree = HashTree(256)

    if not data_folder: 
        # reading hashes from the file
        with open("tests/data/hashes.txt", "r") as hashesf:
            hashes = hashesf.readlines()
            tree |= hashes

    else:
        # reading hashes from the image files in the specified location
        with open("tests/data/hashes.txt", "w") as hashesf:
            for image in data_folder.glob("*.*"):
                meta = CuteMeta.from_file(image)
                try: tree.add(meta.hash)
                except KeyError: continue
                hashesf.write(str(meta.hash) + "\n")
    
    # build tree
    databasef = Path("tests/data/database.db")

    # serialize tree
    with open(databasef, "wb") as database:
        tree.write_to_file(database)