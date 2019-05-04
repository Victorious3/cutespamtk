import argparse
from uuid import UUID
from pathlib import Path

from cutespam import db
from cutespam.meta import CuteMeta

DESCRIPTION = "Outputs a file's tags"

def main(ARGS):
    fp = Path(ARGS.file)
    if fp.exists() and fp.is_file():
        cute_meta = CuteMeta.from_file(fp)
    else:
        try: 
            uid = UUID(ARGS.file)
            cute_meta = CuteMeta.from_db(uid)
        except:
            print("\n".join(str(uid) for uid in db.get_tab_complete_uids(ARGS.file)))
            return

    if ARGS.json:
        print(cute_meta.to_json(ARGS.tag))
    else:
        print(cute_meta.to_string(ARGS.tag))

def args(parser):
    parser.add_argument("--tag", nargs = "+",
        help = "List of tags to include")
    parser.add_argument("--json", action = "store_true",
        help = "Output as json")
    parser.add_argument("file")