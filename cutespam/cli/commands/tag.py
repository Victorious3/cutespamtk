import argparse
import codecs

from datetime import datetime
from pathlib import Path

from cutespam import yn_choice
from cutespam.meta import CuteMeta

DESCRIPTION = "Modify a file's tag values"

def main(ARGS):
    fp = Path(ARGS.file.name)
    tag = ARGS.tag
    cute_meta = CuteMeta.from_file(fp)

    if ARGS.subcommand == "set":
        tpe = getattr(CuteMeta, tag).type
        val = ARGS.value
        # this was in the wrong order, oops
        if len(val) == 1:
            val = val[0]
        if issubclass(tpe, datetime):
            try:
                val = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                print("Invalid date format, use YY-MM-DD HH:MM:SS")
                return

        curr_v = getattr(cute_meta, tag)   
        if curr_v and issubclass(tpe, (list, set)):
            if not yn_choice("You are about to overwrite multiple values, proceed?"): return

        setattr(cute_meta, tag, val)
    elif ARGS.subcommand == "delete":
        setattr(cute_meta, tag, None)
    elif ARGS.subcommand == "add":
        tpe = getattr(CuteMeta, tag).type
        if not issubclass(tpe, (list, set)):
            print("Can only add from list or set")
            return
        v = getattr(cute_meta, tag) or tpe()
        if tpe == list: v += ARGS.value
        else: v |= set(ARGS.value)

        setattr(cute_meta, tag, v)
    elif ARGS.subcommand == "remove":
        tpe = getattr(CuteMeta, tag).type
        if not issubclass(tpe, (list, set)):
            print("Can only remove to list or set")
            return
        v = getattr(cute_meta, tag) or set()
        v = set(v)
        v -= set(ARGS.value)
        setattr(cute_meta, tag, tpe(v))


    cute_meta.write()

def args(parser):

    def unescaped_string(arg_str):
        return codecs.decode(str(arg_str), "unicode_escape")

    tag_subcommand = parser.add_subparsers(dest = "subcommand")

    c_set = tag_subcommand.add_parser("set",
        help = "Modify a file's tags")
    c_set.add_argument("tag",
        help = "Tag to set", choices = CuteMeta.tag_names())
    c_set.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to set. Multiple values for list or set")
    c_set.add_argument("file", type = argparse.FileType())

    c_add = tag_subcommand.add_parser("add",
        help = "Adds an additional value to a tag")
    c_add.add_argument("tag",
        help = "Tag to add to", choices = CuteMeta.tag_names())
    c_add.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to add")
    c_add.add_argument("file", type = argparse.FileType())

    c_remove = tag_subcommand.add_parser("remove",
        help = "Removes a value from a tag")
    c_remove.add_argument("tag",
        help = "Tag to remove from", choices = CuteMeta.tag_names())
    c_remove.add_argument("value", nargs = "+", type = unescaped_string,
        help = "Values to remove")
    c_remove.add_argument("file", type = argparse.FileType())

    c_delete = tag_subcommand.add_parser("delete",
        help = "Deletes a tag completely")
    c_delete.add_argument("tag",
        help = "Tag to remove from", choices = CuteMeta.tag_names())
    c_delete.add_argument("file", type = argparse.FileType())

    return parser