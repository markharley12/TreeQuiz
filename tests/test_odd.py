"""Odd one out: every puzzle has exactly one right answer, and a seed is a set."""
from __future__ import annotations

import pytest
from conftest import n

from treequiz import dataset, odd, seed
from treequiz.game import index


def lineage(ds, label):
    return [x["name"] for x in index(ds).lineage_of[label]]


def shared(ds, a, b):
    la, lb = lineage(ds, a), lineage(ds, b)
    return [x for x, y in zip(la, lb) if x == y][-1]


def assert_resolved(ds, p):
    """The pair meets below where the odd one meets either of them, and both of
    those are the meeting node: one answer, whichever two you compare."""
    a, b = p["pair"]
    c = p["odd"]
    assert sorted(p["choices"]) == sorted([a, b, c])
    assert shared(ds, a, b) == p["group"]["name"]
    assert shared(ds, a, c) == shared(ds, b, c) == p["shared"]["name"]
    assert p["group"]["name"] in lineage(ds, a)[lineage(ds, a).index(p["shared"]["name"]) + 1:]
    assert p["group"]["warmth"] > p["shared"]["warmth"]


@pytest.mark.parametrize("ds_id", dataset.available())
def test_every_puzzle_on_every_tree_has_one_answer_and_no_leaf_twice(ds_id):
    ds = dataset.load(ds_id)
    for k in range(4):
        puzzles = odd.make_set(ds, odd.pick_seed(ds) if k else f"{seed.fingerprint(index(ds).leaves)}-000000")
        assert len(puzzles) == odd.SET_SIZE
        for p in puzzles:
            assert_resolved(ds, p)
        shown = [c for p in puzzles for c in p["choices"]]
        assert len(shown) == len(set(shown))


@pytest.mark.parametrize("ds_id", dataset.available())
def test_a_set_gets_harder_as_it_goes(ds_id):
    ds = dataset.load(ds_id)
    t = odd.tiers(ds)
    assert all(t)
    assert max(m.warmth for m in t[0]) <= min(m.warmth for m in t[1])
    assert max(m.warmth for m in t[1]) <= min(m.warmth for m in t[2])
    tiers = [p["tier"] for p in odd.make_set(ds, odd.pick_seed(ds))]
    assert tiers == sorted(tiers) and tiers[0] == 0 and tiers[-1] == 2


def test_a_seed_is_the_whole_set(zoo):
    s = odd.pick_seed(zoo)
    assert odd.make_set(zoo, s) == odd.make_set(zoo, s.lower().replace("-", " "))
    other = f"{s[:5]}{'ABCDEF' if s[5:] != 'ABCDEF' else 'GHJKMN'}"
    assert odd.make_set(zoo, s) != odd.make_set(zoo, other)


def test_the_days_set_is_the_same_for_everyone(zoo):
    from datetime import date
    day = date(2026, 10, 12)
    assert odd.pick_seed(zoo, daily=True, today=day) == odd.pick_seed(zoo, daily=True, today=day)
    assert odd.pick_seed(zoo, daily=True, today=day) != odd.pick_seed(zoo, daily=True, today=date(2026, 10, 13))


def test_a_seed_from_another_tree_is_refused(zoo):
    with pytest.raises(ValueError, match="different dataset"):
        odd.make_set(zoo, "0000-000000")


def test_the_zoo_puzzles_are_the_ones_a_person_would_set(zoo):
    # Zoo's meeting nodes, coolest first, in thirds. Panthera is not one: its
    # three cats are all equally close. Felidae is hard: two big cats and the
    # domestic cat.
    names = [[m.node["name"] for m in t] for t in odd.tiers(zoo)]
    assert names == [["Animalia"], ["Chordata", "Mammalia"], ["Carnivora", "Felidae"]]
    for p in odd.make_set(zoo, odd.pick_seed(zoo)):
        assert_resolved(zoo, p)


def test_a_tree_with_no_closer_pair_has_no_puzzle():
    flat = dataset.from_tree(n("root", None, n("a"), n("b"), n("c"), n("d")), {"title": "Flat"}, "flat")
    with pytest.raises(ValueError, match="No three"):
        odd.make_set(flat, odd.pick_seed(flat))


def test_a_tree_too_small_for_ten_different_puzzles_repeats_rather_than_failing():
    tiny = dataset.from_tree(n("root", None, n("g", None, n("a"), n("b")), n("c")), {"title": "Tiny"}, "tiny")
    puzzles = odd.make_set(tiny, odd.pick_seed(tiny))
    assert {p["odd"] for p in puzzles} == {"c"}
    assert all(sorted(p["pair"]) == ["a", "b"] for p in puzzles)


def test_the_odd_one_is_shown_in_every_position(animals530):
    ds = animals530
    spots = {p["choices"].index(p["odd"]) for k in range(6) for p in odd.make_set(ds, odd.pick_seed(ds))}
    assert spots == {0, 1, 2}
