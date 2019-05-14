import urllib, time, json, os, sys, subprocess
import logging

from functools import reduce
from pathlib import Path
from enum import Enum
from uuid import UUID
from datetime import datetime

BASE_PATH = Path(__file__).parent

class JSONEncoder(json.JSONEncoder):
    def default(self, obj): # pylint: disable=E0202
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, (UUID, datetime)):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, "__dataclass_fields__"): # dataclass
            return getattr(obj, "__dict__")
        return json.JSONEncoder.default(self, obj)

from cutespam.config import config

log = logging.Logger("db", level = logging.INFO)
if config.trace_debug: 
    log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))

from cutespam.meta import CuteMeta

def open_file(filename):
    if sys.platform == "win32":
        os.startfile(filename)
    else:
        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.call([opener, filename])

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

def decode_all(file):
    return "\n".join(b.decode("utf-8") for b in file.readlines())

def make_request(url, method, ratelimit_retry = False):
    try:
        request = urllib.request.Request(url, headers = {'User-Agent': config.useragent})
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
