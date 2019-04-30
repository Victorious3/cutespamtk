import atexit

from collections.abc import MutableSet
from imagehash import phash
from PIL import Image
from enum import IntEnum

class NodeValue(IntEnum):
    ROOT_NODE = 2
    ZERO = 0
    ONE = 1

class Node:
    def __init__(self, value = NodeValue.ROOT_NODE):
        self.left = None
        self.right = None
        self.value = value

    def __getitem__(self, i):
        if i == 0:
            return self.left
        else:
            return self.right
    
    def __setitem__(self, i, val):
        if i == 0:
            self.left = val
        else:
            self.right = val

    def is_leaf(self):
        return self.right == self.left == None

def _hash_to_int(key):
    if isinstance(key, str):
        key = int(key, 16)
    assert isinstance(key, int)
    return key

class HashTree(MutableSet):
    def __init__(self, hash_length):
        """ hash_length in bits """
        self.root = Node()
        self._len = 0
        self.hash_length = hash_length

    def add(self, key):
        key = _hash_to_int(key)
        bits = format(key, f'0{self.hash_length}b')
        assert len(bits) == self.hash_length

        node = self.root
        for bit in bits:
            bit = int(bit)
            if node[bit]:
                node = node[bit]
            else:
                leaf = Node(NodeValue(bit))
                node[bit] = leaf
                node = leaf
        if not node.is_leaf():
            raise KeyError("Key already exists")

        node.value = key
        self._len += 1

    @staticmethod
    def _serialize_node(node):
        if node:
            yield node.value
            yield from HashTree._serialize_node(node.left)
            yield from HashTree._serialize_node(node.right)
        else: yield None

    def _serialize(self):
        yield from HashTree._serialize_node(self.root)

    @staticmethod
    def _deserialize_node(tree, it):
        v = next(it)
        if v is None: return None

        tree._len += 1
        node = Node(v)
        node.left = HashTree._deserialize_node(tree, it)
        node.right = HashTree._deserialize_node(tree, it)
        return node

    @staticmethod
    def _deserialize(it, hash_length):
        root = Node(next(it))
        tree = HashTree(hash_length)

        root.left = HashTree._deserialize_node(tree, it)
        root.right = HashTree._deserialize_node(tree, it)
        tree.root = root
        return tree

    def discard(self, key):
        key = _hash_to_int(key)
        bits = format(key, f'0{self.hash_length}b')
        assert len(bits) == self.hash_length

        node = self.root
        path = []
        for bit in bits:
            bit = int(bit)
            v = node[bit]
            if v: 
                path.append(node)
                node = v
            else: raise KeyError("Key not found")

        path[-1][bit] = None # Make sure the leaf node is deleted

        # Remove rest of the branch until we hit the first Node that has another branch
        for i in range(len(path)-2, 0, -1): 
            prev = i - 1
            v = int(path[i].value)
            path[prev][v] = None
            if path[prev][~v & 1]: return

        self._len -= 1

    def __contains__(self, key):
        key = _hash_to_int(key)
        bits = format(key, f'0{self.hash_length}b')
        assert len(bits) == self.hash_length
        
        node = self.root
        for bit in bits:
            bit = int(bit)
            v = node[bit]
            if v: node = v
            else: return False
        return True

    @staticmethod
    def _walk(node):
        if not node: return
        if not node.is_leaf():
            yield from HashTree._walk(node.left)
            yield from HashTree._walk(node.right)
        elif node.value:
            yield node.value

    def __iter__(self):
        yield from HashTree._walk(self.root)

    def __len__(self):
        return self._len

@atexit.register
def save_db():
    pass

def hash_img(fp):
    with Image.open(fp) as img_data:
        return str(phash(img_data, hash_size=16))

def hash_meta(cute_meta):
    cute_meta.hash = hash_img(cute_meta.filename)
