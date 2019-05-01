import atexit

from collections.abc import MutableSet
from imagehash import phash
from PIL import Image
from enum import IntEnum
from dataclasses import dataclass

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

    @property
    def key(self):
        return self.left.value

    def is_branch(self):
        return not self.is_leaf()
    
    def is_leaf(self):
        return self.left and not isinstance(self.left.value, NodeValue)

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
        if node.is_leaf():
            raise KeyError("Key already exists")

        node.left = Node(key) # Store the key as degenerate node in left
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

    def _to_bits(self, key):
        bits = format(key, f'0{self.hash_length}b')
        assert len(bits) == self.hash_length
        return [int(bit) for bit in bits]

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
        bits = self._to_bits(key)

        node = self.root
        path = []
        for bit in bits:
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
            if path[prev][~v & 1]: break

        self._len -= 1

    # Algorithm found by me, no credit needed! I'm not sure if its described anywhere else
    # but for the sake of completeness I'll write my thoughts on it down here
    def find_all_hamming_distance(self, key, distance, limit = None):
        return find_all_hamming_distance(self, key, distance, limit)

    def __contains__(self, key):
        key = _hash_to_int(key)
        bits = self._to_bits(key)
        
        node = self.root
        for bit in bits:
            v = node[bit]
            if v: node = v
            else: return False
        return True

    @staticmethod
    def _walk(node):
        if not node: return
        if node.is_branch():
            yield from HashTree._walk(node.left)
            yield from HashTree._walk(node.right)
        else:
            yield node.key

    def __iter__(self):
        yield from HashTree._walk(self.root)

    def __len__(self):
        return self._len


from typing import List

@dataclass
class SeedValue:
    path: List[Node] # length <= hash_length. Could be an array in more efficient implementations
                     # We could also have a parent value for each node but that increases the space requirement elsewhere
    # number of blocked nodes from the start of path. Don't expand those anymore, they have been in a previous iteration
    blocked: int

    def __repr__(self):
        return str(self.blocked) + ": " + "".join(list(str(int(v.value)) for v in self.path[1:]))
        

# Algorithm found by me, no credit needed! I'm not sure if its described anywhere else
# but for the sake of completeness I'll write my thoughts on it down here
def find_all_hamming_distance(tree, key, distance, limit):
    key = _hash_to_int(key)
    bits = tree._to_bits(key)
    hash_length = tree.hash_length

    # find path to key
    node = tree.root
    key_path = [node]
    for bit in bits:
        v = node[bit]
        if v: 
            key_path.append(v)
            node = v
        else: raise KeyError("Key not found")
    key_path = list(key_path)

    seeds = [SeedValue(key_path, 1)] # We need a seed to start from
    results = set()

    for current_distance in range(0, distance): # repeat while current_distance < distance
        if not seeds: break
            
        # print("Iteration", current_distance + 1)
        n_seeds = []  # seeds for the next iteration
        # print("All seeds:", seeds)
        for seed in seeds:
            # print(" Initial seed:", seed)
            k_seeds = []

            for n in range(seed.blocked - 1, len(seed.path) - 1):
                parent = seed.path[n]
                # try to branch out, equivalent to flipping a bit at that position
                branch = parent[~seed.path[n+1].value & 1]
                if not branch: continue
                new_seed = SeedValue(list(seed.path)[:n+2], n + 2) # copy
                new_seed.path[n+1] = branch # flip!
                k_seeds.append(new_seed)

            if len(seed.path) <= hash_length:
                n = len(seed.path)
                # branch out last node
                branch = seed.path[-1][~key_path[n].value & 1]
                if branch:
                    k_seeds.append(SeedValue(list(seed.path) + [branch], n))
                

            # print(" Branched seeds:", k_seeds)

            # grow the seeds by trying to take the same path as key_path from that position
            for new_seed in k_seeds:
                
                # print("  Before:", new_seed)
                for n in range(len(new_seed.path) - 1, hash_length):
                    value = key_path[n + 1].value
                    node = new_seed.path[n][value]
                    if node: 
                        new_seed.path.append(node)
                    
                    else: break
                # print("  After:", new_seed)

                if len(new_seed.path) - 1 == hash_length: # found a result
                    results.add(new_seed.path[-1].key)

                    # if we reached the limit there's no point in continuing, just return the results now
                    if limit is not None and len(results) >= limit: return results
                if new_seed.blocked - 1 < hash_length:
                    n_seeds.append(new_seed)

            # print(" Grown seeds:", n_seeds)
                    
        seeds = n_seeds # set seeds for next iteration

    return results

@atexit.register
def save_db():
    pass

def hash_img(fp):
    with Image.open(fp) as img_data:
        return str(phash(img_data, hash_size=16))

def hash_meta(cute_meta):
    cute_meta.hash = hash_img(cute_meta.filename)
