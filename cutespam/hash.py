import atexit, io
from PIL import Image
from imagehash import phash
from lzma import LZMAFile

from cutespam.hashtree import HashTree

def hash_img(fp): 
    with Image.open(fp) as img_data:
        return str(phash(img_data, hash_size = 16))

def hash_meta(cute_meta):
    cute_meta.hash = hash_img(cute_meta.filename)