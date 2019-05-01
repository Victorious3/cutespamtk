import pytest, random

from cutespam.hash import HashTree

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

def test_find_hamming_distance():
    tree = HashTree(4)
    all_values = set([0b1111, 0b1110, 0b1011, 0b0010, 0b0001, 0b0000])
    tree |= all_values

    assert tree.find_all_hamming_distance(0b1111, 0) == set()
    assert tree.find_all_hamming_distance(0b1111, 1) == set([0b1110, 0b1011])
    assert tree.find_all_hamming_distance(0b1111, 2) == set([0b1110, 0b1011])
    assert tree.find_all_hamming_distance(0b1111, 3) == set([0b1110, 0b1011, 0b0010, 0b0001])
    assert tree.find_all_hamming_distance(0b1111, 4) == all_values - set([0b1111])

    assert tree.find_all_hamming_distance(0b1011, 0) == set()
    assert tree.find_all_hamming_distance(0b1011, 1) == set([0b1111])
    assert tree.find_all_hamming_distance(0b1011, 2) == set([0b1111, 0b1110, 0b0010, 0b0001])
    assert tree.find_all_hamming_distance(0b1011, 3) == all_values - set([0b1011])
    assert tree.find_all_hamming_distance(0b1011, 4) == all_values - set([0b1011])