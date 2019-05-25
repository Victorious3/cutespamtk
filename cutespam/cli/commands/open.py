import argparse
from cutespam.cli import UUIDCompleter

DESCRIPTION = "Opens an image file"

def main(ARGS):
    from uuid import UUID
    from cutespam import open_file
    from cutespam.db import picture_file_for_uid, get_random_uid

    if ARGS.uid:
        uid = UUID(ARGS.uid)
    else: uid = get_random_uid()
    
    path = picture_file_for_uid(uid)
    if ARGS.uri:
        print(path.absolute().as_uri())
    else:
        open_file(path)


def args(parser):
    parser.add_argument("--uri", action = "store_true",
        help = "Outputs the file URI instead of opening it")
    parser.add_argument("uid", nargs = "?").completer = UUIDCompleter
