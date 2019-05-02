import argparse
import validators
import time

from pathlib import Path

from cutespam.iqdb import iqdb as _iqdb
from cutespam.iqdb import IQDBException
from cutespam.meta import CuteMeta

def iqdb(ARGS):
    start = time.time()
    try:
        if validators.url(ARGS.file):
            print("Fetching IQDB for url", ARGS.file, "...")
            results = _iqdb(url = ARGS.file, saucenao = ARGS.saucenao)
        else:
            cute_meta = CuteMeta.from_file(Path(ARGS.file))
            if cute_meta.source:
                print("Fetching IQDB for url", cute_meta.source, "...")
                results = _iqdb(url = cute_meta.source, saucenao = ARGS.saucenao)
            else:
                print("Fetching IQDB for file", ARGS.file, "...")
                results = _iqdb(file = open(ARGS.file, "rb"), saucenao = ARGS.saucenao)

        end = time.time()
        print(f"Found {len(results)} results in {end - start:.2f} seconds.")
        for index, result in enumerate(results):
            print(f"{index+1:>3}: {result.similarity:.0%} {result.size[0]:>4}x{result.size[1]:<4} [{result.rating:^8}] {result.url}")
    except IQDBException as e:
        print("IQDB Error:", str(e))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help = "Specify file to look for or url to do iqdb search")
    parser.add_argument("--saucenao", action = "store_true", help = "Add search results from saucenao.com")
    # parser.add_argument("--json", action = "store_true", help = "Output as json")
    
    ARGS = parser.parse_args()
    iqdb(ARGS)

if __name__ == "__main__":
    main()