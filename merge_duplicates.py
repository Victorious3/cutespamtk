#!/usr/bin/env python3

import os

from pathlib import Path
from cutespam import find_duplicates, all_files_in_folders, CuteMeta
from importer import Provider, DanbooruImage, DanbooruImageFmt2
from PIL import Image
from functools import reduce
from uuid import UUID, uuid4

FOLDERS = [
    #"../",
    #"../unsourced/todo",
    #"../from_old_phone/download/",
    #"../from_old_phone/pictures/",
    #"../from_old_phone/twitter/",
    #"../redownload/",
]

OUT_FOLDER = "../"

if __name__ == "__main__":
    duplicates = find_duplicates(all_files_in_folders(FOLDERS))

    class SortKeyFile:
        def __init__(self, entry):
            self.file = entry.file

        def __lt__(self, other):
            f1 = self.file
            f2 = other.file

            fsize1 = os.path.getsize(f1.resolve())
            fsize2 = os.path.getsize(f2.resolve())

            with Image.open(f1) as img_data:
                width, height = img_data.size
                res1 = width * height
                format1 = img_data.format
            with Image.open(f2) as img_data:
                width, height = img_data.size
                res2 = width * height
                format2 = img_data.format
            
            if res1 == res2:
                if format1 == format2:
                    if abs(fsize1 - fsize2) < 10000:
                        return len(str(f1)) > len(str(f2))
                    return fsize1 < fsize2
                else:
                    if format1 == "PNG": return False
                    else: return True
            else:
                return res1 < res2

    class SortKeyProvider:
        def __init__(self, entry):
            self.provider = entry.provider
        
        def __lt__(self, other):
            if not self.provider: return True
            elif not other.provider: return False
            else: return self.provider < other.provider
        
    class Entry:
        def __init__(self, file, meta):
               self.file = file
               self.meta = meta
               self.provider = Provider.for_url(meta.source) if meta.source else None

    for duplicte in duplicates:
        metas = [Entry(f, CuteMeta.from_file(f)) for f in duplicte]
        metas = sorted(metas, key = SortKeyFile, reverse = True)

        best_file = metas[0].file
        meta = metas[0].meta
        
        if not getattr(meta, "source", None):
            meta.source = sorted(metas, key = SortKeyProvider, reverse = True)[0].provider.url
        
        danbooru_providers = list(filter(lambda m: isinstance(m.provider, (DanbooruImage, DanbooruImageFmt2)), metas))
        if danbooru_providers:
            meta.uid = danbooru_providers[0].meta.uid
        if not meta.uid:
            meta.uid = uuid4()

        def find_all_keys_set(key):
            s = reduce(lambda a, b: a | b, filter(None.__ne__, [getattr(m.meta, key, None) for m in metas]), set())
            s = s or None
            return s
        def find_first_key(key):
            ls = list(filter(None.__ne__, [getattr(m.meta, key, None) for m in metas]))
            return ls[0] if len(ls) > 0 else None

        meta.caption = find_first_key("caption")
        meta.author = find_first_key("author")
        meta.keywords = find_all_keys_set("keywords")
        meta.group_id = find_first_key("group_id")
        meta.collections = find_all_keys_set("collections")
        meta.rating = find_first_key("rating")
        meta.date = find_first_key("date")
        meta.source_other = find_all_keys_set("source_other")
        meta.source_via = find_all_keys_set("source_via")

        new_name = best_file.parent / (str(meta.uid) + best_file.suffix)
        to_delete = [e.file for e in metas[1:]]

        print("I chose", best_file, "from", duplicte)
        print("Renaming to", new_name)
        print("Deleting", to_delete)
        print(meta)

        meta.write()
        if not new_name.exists():
            os.rename(best_file.resolve(), new_name.resolve())
        for f in to_delete:
            os.remove(f.resolve())
        
