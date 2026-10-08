"""Seeds, and explore's slices, lineages and search."""
from __future__ import annotations

import pytest

from treequiz import explore, seed
from treequiz.tree import leaves


def test_a_seed_from_another_tree_is_rejected_not_reinterpreted(zoo):
    other = [{"name": "x"}, {"name": "y"}]
    s = seed.make_seed(other)
    with pytest.raises(ValueError, match="different dataset"):
        seed.resolve(s, leaves(zoo.tree))


def test_fingerprint_follows_labels_and_order():
    a = [{"name": "1", "label": "lion"}, {"name": "2", "label": "tiger"}]
    assert seed.fingerprint(a) != seed.fingerprint(list(reversed(a)))
    assert seed.fingerprint(a) == seed.fingerprint([{"name": "lion"}, {"name": "tiger"}])


@pytest.mark.parametrize("bad", ["", "ABCD-2345", "ABCD-23456789"])
def test_normalise_rejects_the_wrong_length(bad):
    with pytest.raises(ValueError, match="not a seed"):
        seed.normalise(bad)


def test_seeds_avoid_ambiguous_letters():
    assert not set("ILOU") & set(seed.ALPHABET)


def test_a_budget_stops_before_a_level_would_exceed_it(zoo):
    s = explore.subtree(zoo, budget=3)
    assert [c["name"] for c in s["children"]] == ["Chordata", "Cnidaria"]
    assert all(c["truncated"] and not c["children"] for c in s["children"])


def test_every_node_counts_its_leaves(zoo):
    s = explore.subtree(zoo, budget=None)
    assert s["leaf_count"] == 8
    assert s["children"][0]["label"] == "Chordata" and s["children"][0]["leaf_count"] == 7


def test_unknown_root_raises(zoo):
    with pytest.raises(ValueError, match="Not in this dataset"):
        explore.subtree(zoo, "Nowhere")


def test_lineage_opens_the_path_with_siblings_as_stubs(zoo):
    out = explore.lineage(zoo, "Panthera")
    assert out["path"][-1] == "Panthera" and out["path"][0] == "Animalia"
    root = out["tree"]
    assert {c["name"] for c in root["children"]} == {"Chordata", "Cnidaria"}
    cnidaria = next(c for c in root["children"] if c["name"] == "Cnidaria")
    assert cnidaria["truncated"] and cnidaria["children"] == []


def test_search_matches_labels_names_and_aliases(zoo):
    assert [h["name"] for h in explore.search(zoo, "lion")] == ["Panthera leo"]
    assert [h["name"] for h in explore.search(zoo, "panthera")][0] == "Panthera"   # bigger group first
    assert explore.search(zoo, "  ") == []


def test_stats(zoo):
    assert explore.stats(zoo) == {"root": "Animalia", "nodes": 23, "leaves": 8, "max_depth": 6}
