import argparse
from cutespam.meta import CuteMeta # This is needed for below

DESCRIPTION = "Filters filenames for tags or properties"

def main(ARGS):
    from cutespam.db import get_all_uids, filename_for_uid

    filtered = []
    for uid in get_all_uids():
        cute_meta = CuteMeta.from_db(uid)

        keywords = cute_meta.keywords or set()
        if ARGS.keyword and not set(ARGS.keyword).issubset(keywords): continue
        if ARGS.not_keyword and set(ARGS.not_keyword).intersection(keywords): continue
        filtered.append(uid)

    for uid in filtered:
        print(filename_for_uid(uid).absolute().as_uri() if ARGS.uri else uid)

def args(parser):
    parser.add_argument("--uri", action = "store_true",
         help = "Emits absolute file:// URIs instead of relative paths")
    parser.add_argument("--keyword", nargs = "+", default = [],
        help = "Filters for keywords")
    parser.add_argument("--not-keyword", nargs = "+", default = [],
        help = "Filters for missing missing keywords")