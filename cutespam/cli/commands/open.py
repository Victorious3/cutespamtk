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
    open_file(str(picture_file_for_uid(uid)))


def args(parser):
    parser.add_argument("uid", nargs = "?").completer = UUIDCompleter
