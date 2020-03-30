import argparse
from cutespam.cli import KeywordCompleter

DESCRIPTION = "Queries uids from keyword"

def main(ARGS):
    from cutespam import db
    keywords = list(db.get_tab_complete_keywords(ARGS.keyword))

    if len(keywords) == 1 and keywords[0] == ARGS.keyword:
        uids = db.get_uids_from_keyword(keywords[0])
        for uid in uids:
            print(uid)
    else:
        for keyword in keywords:
            print(keyword)

def args(parser):
    parser.add_argument("keyword", help = "keyword to search for").completer = KeywordCompleter