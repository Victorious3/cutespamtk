import argparse
from cutespam.cli import UUIDCompleter

DESCRIPTION = "Imports an image file. Uses IQDB to fetch metadata"

def main(ARGS):
    from cutespam.iqdb import iqdb, upscale

def args(parser):
    parser.add_argument("file", type = argparse.FileType)
