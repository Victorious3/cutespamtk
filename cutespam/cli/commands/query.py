import argparse
from cutespam.xmpmeta import CuteMeta # This is needed for below

DESCRIPTION = "Queries uids for tags or properties"

def main(ARGS):
    from cutespam.db import query, picture_file_for_uid
    import json

    filtered = query(
        keyword = ARGS.keyword, 
        not_keyword = ARGS.not_keyword, 
        author = ARGS.author,
        caption = ARGS.caption,
        source = ARGS.source,
        rating = ARGS.rating,
        limit = ARGS.limit,
        random = ARGS.random
    )

    if ARGS.count:
        print(len(filtered))
    else:
        l = [(picture_file_for_uid(uid).absolute().as_uri() if ARGS.uri else str(uid)) for uid in filtered]
        if ARGS.json:
            print(json.dumps(l, indent = 4))
        else:
            print("\n".join(l))


def args(parser):
    parser.add_argument("--json", action = "store_true",
        help = "Outputs a json array instead of an unformatted list")
    parser.add_argument("--uri", action = "store_true",
        help = "Emits absolute file:// URIs instead of relative paths")
    parser.add_argument("--limit", type = int,
        help = "Limits the amount of results")
    parser.add_argument("--random", action = "store_true",
        help = "Orders the results randomly")
    parser.add_argument("--count", action = "store_true",
        help = "Count the number of results instead of emitting them")
    parser.add_argument("--author",
        help = "Filters for author")
    parser.add_argument("--caption",
        help = "Filters for caption")
    parser.add_argument("--source",
        help = "Filters for source")
    parser.add_argument("--rating",
        help = "Filters for rating")
    parser.add_argument("--keyword", nargs = "+", default = [],
        help = "Filters for keywords")
    parser.add_argument("--not-keyword", nargs = "+", default = [],
        help = "Filters for missing missing keywords")