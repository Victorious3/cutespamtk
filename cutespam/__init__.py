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
log_formatter = logging.Formatter("%(asctime)s [%(module)s][%(levelname)s]: %(message)s")

if config.trace_debug: 
    log.setLevel(logging.DEBUG)

sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(log_formatter)
log.addHandler(sh)

from cutespam.xmpmeta import CuteMeta

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
                print("Rate limit exceeded on %s, will retry after %s seconds" % (url, seconds))
                time.sleep(seconds)
                return make_request(request, url)
            else:
                raise Exception("Rate limit exceeded on", url, ", skipping")

import queue
import collections

# http://code.activestate.com/recipes/576694/ by Raymond Hettinger

class OrderedSet(collections.abc.MutableSet):
    def __init__(self, iterable=None):
        self.end = end = [] 
        end += [None, end, end]         # sentinel node for doubly linked list
        self.map = {}                   # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:        
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)

# https://stackoverflow.com/questions/16506429/check-if-element-is-already-in-a-queue by abarnert

class OrderedSetQueue(queue.Queue):
    def _init(self, maxsize):
        self.queue = OrderedSet()

    def _put(self, item):
        self.queue.add(item)
        
    def _get(self):
        return self.queue.pop()
