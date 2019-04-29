import argparse
from pathlib import Path

from cutespam.meta import CuteMeta

DESCRIPTION = "Outputs a file's tags"

def main(ARGS):
    fp = Path(ARGS.file.name)
    cute_meta = CuteMeta.from_file(fp)

    if ARGS.json:
        print(cute_meta.to_json(ARGS.tag))
    else:
        print(cute_meta.to_string(ARGS.tag))

def args(parser):
    parser.add_argument("--tag", nargs = "+",
        help = "List of tags to include")
    parser.add_argument("--json", action = "store_true",
        help = "Output as json")
    parser.add_argument("file", type = argparse.FileType())