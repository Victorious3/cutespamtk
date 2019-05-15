from cutespam.cli import UUIDCompleter, argrange

DESCRIPTION = "Finds similar images indicated by a threshold"

def main(ARGS):
    from uuid import UUID

    from cutespam.db import find_similar_images, picture_file_for_uid

    uuid = UUID(ARGS.uuid)
    result = find_similar_images(uuid, ARGS.threshold / 100, ARGS.limit)
    for r in result:
        uid = r[1]
        if ARGS.uri:
            uid = picture_file_for_uid(uid).absolute().as_uri()
        print(f"{r[0]:.1%}: {uid}")

def args(parser):
    parser.add_argument("uuid").completer = UUIDCompleter
    parser.add_argument("--uri", action = "store_true",
         help = "Emits absolute file:// URIs instead of relative paths")
    parser.add_argument("-t", "--threshold", default = 90, type = int, choices = argrange(0, 100), metavar = "[0-100]")
    parser.add_argument("-l", "--limit", default = 100, type = int, choices = argrange(1, 100), metavar = "[1-100]")