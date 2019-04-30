import atexit

from imagehash import phash
from PIL import Image

from bintrees.abctree import ABCTree
from bintrees.bintree import Node

class HashTree(ABCTree):
    def insert(self, key, value = None):
        if not value: 
            value = key

        if isinstance(key, str):
            key = int(key, 16)
        assert isinstance(key, int), "Can only work with hex strings or ints as keys"

        bits = bin(key)
        if self._root is None:
            self._root = Node(None, None)
        
        node = self._root
        for bit in bits:
            pass

    def remove(self, key):
        pass

@atexit.register
def save_db():
    pass

def hash_img(fp):
    with Image.open(fp) as img_data:
        return str(phash(img_data, hash_size=16))

def hash_meta(cute_meta):
    cute_meta.hash = hash_img(cute_meta.filename)
