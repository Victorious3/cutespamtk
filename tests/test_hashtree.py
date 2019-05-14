import pytest, random

from cutespam.hashtree import HashTree

def test_hash_tree_insert():
    tree = HashTree(256)
    tree.add(0xf9101c9eb59dace6cbcef38fa433a6338683c759c268c4ec51883155cb2a53f8)
    tree.add(0xed8a30cbb2d133170f36d32cd32c02dc93cbd903ccb68cb29b70db6ce728a6d1)

    assert 0xf9101c9eb59dace6cbcef38fa433a6338683c759c268c4ec51883155cb2a53f8 in tree
    assert 0xed8a30cbb2d133170f36d32cd32c02dc93cbd903ccb68cb29b70db6ce728a6d1 in tree

    assert 0xfefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefe not in tree
    assert 0x0000000000000000000000000000000000000000000000000000000000000000 not in tree

def test_hash_tree_walk():
    tree = HashTree(8)
    tree.add(0xF)
    tree.add(0xA)

    assert len(tree) == 2
    assert list(tree) == [0xA, 0xF]

def test_hash_tree_remove():
    tree = HashTree(256)
    rndints = []
    for _ in range(0, 20):
        rndint = random.getrandbits(256)
        rndints.append(rndint)
        tree.add(rndint)

    for r in list(reversed(rndints)):
        rndints.pop()
        assert r in tree
        tree.remove(r)
        assert r not in tree

        for other in rndints:
            assert other in tree
    
    assert len(tree) == 0
    assert tree.root.left == tree.root.right == None

def test_tree_serialization():
    tree = HashTree(256)
    for _ in range(0, 30):
        tree.add(random.getrandbits(256))

    first = list(tree._serialize())
    tree2 = HashTree._deserialize(iter(first), tree.hash_length)
    second = list(tree2._serialize())

    assert first == second

def find_all_hamming_distance(tree, *args):
    return set(v[1] for v in tree.find_all_hamming_distance(*args))

# Test on known trees
def test_find_hamming_distance_simple():
    tree = HashTree(4)
    all_values = set([0b1111, 0b1110, 0b1011, 0b0010, 0b0001, 0b0000])
    tree |= all_values

    assert find_all_hamming_distance(tree, 0b1111, 0) == set()
    assert find_all_hamming_distance(tree, 0b1111, 1) == set([0b1110, 0b1011])
    assert find_all_hamming_distance(tree, 0b1111, 2) == set([0b1110, 0b1011])
    assert find_all_hamming_distance(tree, 0b1111, 3) == set([0b1110, 0b1011, 0b0010, 0b0001])
    assert find_all_hamming_distance(tree, 0b1111, 4) == all_values - set([0b1111])

    assert find_all_hamming_distance(tree, 0b1011, 0) == set()
    assert find_all_hamming_distance(tree, 0b1011, 1) == set([0b1111])
    assert find_all_hamming_distance(tree, 0b1011, 2) == set([0b1111, 0b1110, 0b0010, 0b0001])
    assert find_all_hamming_distance(tree, 0b1011, 3) == all_values - set([0b1011])
    assert find_all_hamming_distance(tree, 0b1011, 4) == all_values - set([0b1011])

# Test on random hashes
def test_find_hamming_distance():
    tree = HashTree(54)
    numbers = []

    def create_offset(n):
        num = 0b000000_000000_000000_000000
        for m in range(0, 6):   num ^= (((n & 0b0001) >> 0) & 1) << m
        for m in range(6, 12):  num ^= (((n & 0b0010) >> 1) & 1) << m
        for m in range(12, 18): num ^= (((n & 0b0100) >> 2) & 1) << m
        for m in range(18, 24): num ^= (((n & 0b1000) >> 3) & 1) << m
        return num

    for i in range(0, 16):
        num = random.getrandbits(30) << 24 | create_offset(i)
        tree.add(num)
        number = (num, [])
        for m in random.sample(range(24, 54), 5):
            num = num ^ (1 << m)
            number[1].append(num)
            tree.add(num)
        numbers.append(number)

    newline = "\n"
    fmt = "054b"
    print()
    print("\n\n".join(f"{n[0]:{fmt}} >>>\n{newline.join(f'{o:{fmt}}' for o in n[1])}" for n in numbers))

    for n in numbers:
        find = n[0]
        test = n[1]
        for distance in range(0, len(test)):
            assert find_all_hamming_distance(tree, find, distance) == set(test[:distance])
    