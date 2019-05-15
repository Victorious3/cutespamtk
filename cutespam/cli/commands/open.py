import argparse
from cutespam.cli import UUIDCompleter

DESCRIPTION = "Opens an image file"

def main(ARGS):
    import os
    from uuid import UUID
    from cutespam import open_file
    from cutespam.db import picture_file_for_uid

    uid = UUID(ARGS.uid)
    open_file(str(picture_file_for_uid(uid)))


def args(parser):
    parser.add_argument("uid").completer = UUIDCompleter
