import urllib, time

from functools import reduce
from pathlib import Path

from cutespam.meta import CuteMeta

PROBE_USERAGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/73.0.3683.75 Chrome/73.0.3683.75 Safari/537.3"
CHUNK_SIZE = 4096

def partition(p, l):
    return reduce(lambda x, y: x[not p(y)].append(y) or x, l, ([], []))

def yn_choice(message, default='n'):
    choices = 'Y/n' if default.lower() in ('y', 'yes') else 'y/N'
    choice = input("%s (%s) " % (message, choices))
    values = ('y', 'yes', '') if choices == 'Y/n' else ('y', 'yes')
    return choice.strip().lower() in values

def all_files_in_folders(folders):
    for folder in folders:
        for f in Path(folder).glob("*"):
            if f.name.startswith("."): continue
            if f.is_file(): yield f

def find_duplicates(files): # TODO Move this elsewhere
    ALL_HASHES = {}
    duplicates = []

    for f in files:
        try:
            meta = CuteMeta.from_file(f)
        except TypeError: continue

        h = meta.hash
        if h in ALL_HASHES.keys():
            hashes = ALL_HASHES[h]
            if len(hashes) == 1:
                duplicates.append(hashes)
            hashes.append(f)
        else:
            ALL_HASHES[h] = [f]

    return duplicates

def decode_all(file):
    return "\n".join(b.decode("utf-8") for b in file.readlines())

def make_request(url, method, ratelimit_retry = False):
    try:
        request = urllib.request.Request(url, headers = {'User-Agent': PROBE_USERAGENT})
        request.get_method = lambda: method
        response = urllib.request.urlopen(request)
        return response
    except urllib.error.HTTPError as e:
        if e.code == 429:
            headers = response.info().headers
            if "Retry-After" in headers:
                seconds = headers["Retry-After"] + 10
            else:
                seconds = 120

            if ratelimit_retry:
                print("Rate limit exceeded on", url, ", will retry after", seconds, "seconds")
                time.sleep(seconds)
                return make_request(request, url)
            else:
                raise Exception("Rate limit exceeded on", url, ", skipping")

from cutespam.api import *
