import sqlite3

from cutespam.hashtree import HashTree

from uuid import UUID

__hashes: HashTree
__db: sqlite3.Connection

def sync_metadata(cute_meta):
    pass

def find_similar_images(uid, threshold, limit = 10):
    """ returns a list of uids for similar images for an image/uid """