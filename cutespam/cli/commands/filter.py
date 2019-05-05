import sys
import fileinput
import argparse
from cutespam.meta import CuteMeta # This is needed for below


DESCRIPTION = "Filters filenames for tags or properties"

def main(ARGS):
    from glob import glob
    from pathlib import Path

    def print_path(fp):
        if ARGS.uri:
            print(Path(fp).absolute().as_uri())
        else:
            print(fp)

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

def args(parser):
    parser.add_argument("--uri", action = "store_true",
         help = "Emits absolute file:// URIs intead of relative paths")
    parser.add_argument("--tag", nargs = "+", default = [], choices = CuteMeta.tag_names(),
        help = "Filters for tags")
    parser.add_argument("--not-tag", nargs = "+", default = [],
        help = "Filters for missing tags")
    parser.add_argument("files", nargs = "*",
        help = "Files to filter")