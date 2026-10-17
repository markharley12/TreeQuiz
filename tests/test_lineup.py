"""Line-up: every puzzle has exactly one right order, and a seed is a set."""
from __future__ import annotations

import pytest
from conftest import n

from treequiz import dataset, lineup, seed
from treequiz.game import index
from treequiz.tree import children_of


def lineage(ds, label):
    return [x["name"] for x in index(ds).lineage_of[label]]


def meet(ds, a, b):
    return [x for x, y in zip(lineage(ds, a), lineage(ds, b)) if x == y][-1]


def assert_resolved(ds, p):
    """Each option meets the target where the puzzle says, the four places are
    different ancestors, and the nearest meets deepest: one right order."""
    assert sorted(p["choices"]) == sorted(p["order"]) and len(set(p["order"])) == lineup.OPTIONS
    assert p["target"] not in p["order"]
    line = lineage(ds, p["target"])
    depths = []
    for option, m in zip(p["order"], p["meets"]):
        assert meet(ds, p["target"], option) == m["name"]
        depths.append(line.index(m["name"]))
    assert depths == sorted(depths, reverse=True) and len(set(depths)) == lineup.OPTIONS
    warmths = [m["warmth"] for m in p["meets"]]
    assert warmths == sorted(warmths, reverse=True) and len(set(warmths)) == lineup.OPTIONS


@pytest.mark.parametrize("ds_id", dataset.available())
def test_every_puzzle_on_every_tree_has_one_order_and_no_leaf_twice(ds_id):
    ds = dataset.load(ds_id)
    for k in range(4):
        puzzles = lineup.make_set(ds, lineup.pick_seed(ds) if k else f"{seed.fingerprint(index(ds).leaves)}-000000")
        assert len(puzzles) == lineup.SET_SIZE
        for p in puzzles:
            assert_resolved(ds, p)
        shown = [x for p in puzzles for x in [p["target"], *p["choices"]]]
        assert len(shown) == len(set(shown))


@pytest.mark.parametrize("m,tier,w", [(15, 0, 15), (15, 1, 10), (15, 2, 5), (6, 1, 4), (5, 2, 4), (4, 0, 4), (4, 2, 4)])
def test_a_harder_tier_draws_from_fewer_of_the_deepest_levels(m, tier, w):
    assert lineup.window(m, tier) == w


def test_a_hard_puzzle_meets_the_target_near_it():
    ds = dataset.load("plants")
    for p in lineup.make_set(ds, lineup.pick_seed(ds)):
        line = lineage(ds, p["target"])
        levels = lineup._levels(index(ds).lineage_of[p["target"]], lineup.shape(ds).span)
        deepest = [line[d] for d in levels[len(levels) - lineup.window(len(levels), p["tier"]):]]
        assert all(m["name"] in deepest for m in p["meets"])


def test_a_level_needs_another_branch():
    # Canis and Canidae hold only the wolf, so nothing meets the wolf there;
    # Primates holds only people.
    ds = dataset.load("animals")
    for p in lineup.make_set(ds, lineup.pick_seed(ds)):
        for m in p["meets"]:
            assert len(children_of(index(ds).lineage_of[p["target"]][lineage(ds, p["target"]).index(m["name"])])) >= 2


def test_the_wolfs_line_up_is_the_one_a_person_would_set(zoo):
    # The wolf has four levels: Carnivora (a cat), Mammalia (a person),
    # Chordata (a sparrow), Animalia (a jellyfish). Whatever the seed, that is
    # the order.
    cats = {"lion", "tiger", "leopard", "domestic cat"}
    seen = 0
    for k in range(40):
        for p in lineup.make_set(zoo, lineup.pick_seed(zoo)):
            assert_resolved(zoo, p)
            if p["target"] == "grey wolf":
                seen += 1
                assert p["order"][0] in cats and p["order"][1:] == ["human", "house sparrow", "moon jelly"]
    assert seen


def test_only_leaves_with_four_levels_are_targets(zoo):
    labels = sorted(x.get("label", x["name"]) for x in lineup.shape(zoo).eligible)
    assert labels == ["domestic cat", "grey wolf", "leopard", "lion", "tiger"]


def test_a_seed_is_the_whole_set(zoo):
    s = lineup.pick_seed(zoo)
    assert lineup.make_set(zoo, s) == lineup.make_set(zoo, s.lower().replace("-", " "))
    other = f"{s[:5]}{'ABCDEF' if s[5:] != 'ABCDEF' else 'GHJKMN'}"
    assert lineup.make_set(zoo, s) != lineup.make_set(zoo, other)


def test_a_seed_from_another_tree_is_refused(zoo):
    with pytest.raises(ValueError, match="different dataset"):
        lineup.make_set(zoo, "0000-000000")


def test_a_tree_with_no_leaf_four_levels_deep_has_no_line_up():
    shallow = dataset.from_tree(n("root", None, n("g", None, n("a"), n("b")), n("c")), {"title": "Shallow"}, "shallow")
    with pytest.raises(ValueError, match="No leaf"):
        lineup.make_set(shallow, lineup.pick_seed(shallow))


def test_a_tree_too_small_for_five_different_puzzles_repeats_rather_than_failing():
    comb = dataset.from_tree(n("r", None, n("a"), n("g1", None, n("b"), n("g2", None, n("c"), n("g3", None, n("d"), n("e"))))),
                             {"title": "Comb"}, "comb")
    for p in lineup.make_set(comb, lineup.pick_seed(comb)):
        assert_resolved(comb, p)
        assert p["order"] == (["e", "c", "b", "a"] if p["target"] == "d" else ["d", "c", "b", "a"])


def test_the_nearest_is_shown_in_every_position():
    ds = dataset.load("cities")
    spots = {p["choices"].index(p["order"][0]) for k in range(8) for p in lineup.make_set(ds, lineup.pick_seed(ds))}
    assert spots == {0, 1, 2, 3}


def test_a_ranking_scores_a_point_for_each_in_its_place():
    p = {"order": ["a", "b", "c", "d"]}
    assert lineup.score(p, ["a", "b", "c", "d"]) == 4
    assert lineup.score(p, ["b", "a", "c", "d"]) == 2
    assert lineup.score(p, ["d", "c", "b", "a"]) == 0
