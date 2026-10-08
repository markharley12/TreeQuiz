"""Warmth: the anchors, belief in ranks, interpolation, and strict ordering."""
from __future__ import annotations

from conftest import n

from treequiz.dataset import Ladder
from treequiz.ladder import believed_levels, rejected_share, warmth_by_name

LINNAEAN = Ladder({"kingdom": 0, "phylum": 1, "class": 2, "subclass": 2.3, "order": 3,
                   "family": 4, "genus": 5, "subkingdom": 0.3, "species": 6}, 6)


def edges(node, parent=None):
    yield node, parent
    for c in node.get("children") or []:
        yield from edges(c, node)


def test_root_is_cold_and_leaves_are_hot_whatever_their_ranks_say():
    # A root ranked "class" (2/6 on the ladder) would make every guess look a
    # third of the way there; a leaf ranked "genus" would make finding it 5/6.
    tree = n("Mammalia", "class", n("Felidae", "family", n("Panthera", "genus", n("lion", "genus"))),
             n("Canis", "genus"))
    w = warmth_by_name(tree, LINNAEAN)
    assert w["Mammalia"] == 0.0
    assert w["lion"] == w["Canis"] == 1.0


def test_with_no_ladder_every_node_is_placed_by_the_shape():
    tree = n("root", None,
             n("a", None, n("a1", None, n("a1x")), n("a2")),
             n("b"))
    w = warmth_by_name(tree, Ladder())
    assert w["root"] == 0.0 and w["a2"] == w["b"] == w["a1x"] == 1.0
    assert 0.0 < w["a"] < w["a1"] < 1.0


def test_a_tie_below_is_broken_toward_the_longer_path():
    # "a" has leaves one and three steps down. Placed against the near one it
    # would be halfway; against the far one, a quarter. TaxoQuiz took whichever
    # child came first, so the answer depended on sort order.
    deep_first = n("root", None, n("a", None, n("x", None, n("y", None, n("deep"))), n("near")))
    near_first = n("root", None, n("a", None, n("near"), n("x", None, n("y", None, n("deep")))))
    for tree in (deep_first, near_first):
        assert warmth_by_name(tree, Ladder())["a"] == 0.25


def test_contradicting_ranks_are_both_distrusted():
    # A subclass containing a class: neither claim can be right, and believing
    # the ancestor would flatten everything below it (TaxoQuiz's Mammalia bug).
    tree = n("Animalia", "kingdom",
             n("Tetrapodomorpha", "subclass",
               n("Mammalia", "class", n("Carnivora", "order", n("lion", "species")))))
    believed = believed_levels(tree, LINNAEAN)
    by_name = {node["name"]: believed[id(node)] for node, _ in edges(tree)}
    assert by_name["Tetrapodomorpha"] is None and by_name["Mammalia"] is None
    assert by_name["Carnivora"] == 3
    assert rejected_share(tree, LINNAEAN) == (2, 3)


def test_equal_ranks_nested_are_rejected_not_tied():
    tree = n("Animalia", "kingdom",
             n("Eumetazoa", "subkingdom",
               n("Bilateria", "subkingdom", n("wasp", "species")),
               n("coral", "species")))
    w = warmth_by_name(tree, LINNAEAN)
    assert w["Animalia"] < w["Eumetazoa"] < w["Bilateria"]


def test_going_down_is_strictly_warmer_on_every_edge():
    # The crossing case: B sees its broadest rank five steps away, and on its
    # own would land colder than A above it.
    tree = n("Mammalia", "class",
             n("A", "clade",
               n("Near", "subclass", n("near sp", "species")),
               n("B", "clade", n("B1", "clade", n("B2", "clade",
                 n("Far", "subclass", n("far sp", "species")))))))
    w = warmth_by_name(tree, LINNAEAN)
    for node, parent in edges(tree):
        if parent is not None:
            assert w[node["name"]] > w[parent["name"]], (parent["name"], node["name"])


def test_rank_lookup_ignores_case_and_whitespace():
    assert LINNAEAN.level_of(" Genus ") == 5
    assert LINNAEAN.level_of("clade") is None
    assert LINNAEAN.level_of(None) is None


def test_ladder_from_manifest_defaults_top_to_the_highest_level():
    assert Ladder.from_manifest({"levels": {"A": 0, "B": 3}}).top == 3
    assert Ladder.from_manifest(None) == Ladder()
