"""A tree cut to its best-known leaves, and a manifest's sizes."""
from __future__ import annotations

import io
import json

import pytest
from conftest import n

from treequiz import cli, dataset, explore, game, lineup, odd, seed
from treequiz.ladder import warmth_by_name
from treequiz.size import Sizes, cut, entry_ranks, ranked, tiers
from treequiz.tree import all_nodes, label_of, leaves
from treequiz.validate import validate


def f(name, fame, **extra):
    return n(name, None, fame=fame, **extra)


# Fame chosen so the order is a, then b and c tied (b first by name), then d,
# e... A pass-through (solo) above a lone famous leaf, and a group (dim) whose
# leaves all go early.
FAMED = n("root", None,
          n("big", None, f("a", 90), n("mid", None, f("c", 50), f("d", 40), f("e", 5))),
          n("solo", None, n("lone", None, f("b", 50))),
          n("dim", None, f("x", 3), f("y", 2)),
          f("z", 1))

SIZES = {"min": 2, "default": 4, "stops": [2, 4, 6]}


def names(tree):
    return [x["name"] for x in all_nodes(tree)]


def test_ranked_is_fame_then_name():
    assert [x["name"] for x in ranked(FAMED)] == ["a", "b", "c", "d", "e", "x", "y", "z"]


def test_a_cut_keeps_the_best_known_and_what_holds_them():
    assert names(cut(FAMED, 1)) == ["root", "big", "a"]
    # b ties c on fame and wins by name; its pass-throughs come with it.
    assert names(cut(FAMED, 2)) == ["root", "big", "a", "solo", "lone", "b"]
    assert names(cut(FAMED, 3)) == ["root", "big", "a", "mid", "c", "solo", "lone", "b"]
    assert [x["name"] for x in leaves(cut(FAMED, 6))] == ["a", "c", "d", "e", "b", "x"]


def test_a_cut_leaves_pass_throughs_as_they_are():
    # mid is left with one child at 3, as TaxoQuiz's threshold builds left a
    # genus with one species above the line.
    mid = next(x for x in all_nodes(cut(FAMED, 3)) if x["name"] == "mid")
    assert [c["name"] for c in mid["children"]] == ["c"]


def test_the_whole_tree_is_the_same_object_and_untouched_parts_are_shared():
    assert cut(FAMED, 8) is FAMED
    assert cut(FAMED, 100) is FAMED
    small = cut(FAMED, 6)
    assert small["children"][1] is FAMED["children"][1]   # solo, whole
    assert small["children"][0] is FAMED["children"][0]   # big, whole
    assert "fame" in leaves(small)[0]
    # The input is never touched.
    assert len(leaves(FAMED)) == 8


def test_a_leaf_with_no_fame_counts_as_none():
    tree = n("r", None, n("p"), f("q", 1))
    assert names(cut(tree, 1)) == ["r", "q"]


def test_nothing_is_not_a_size():
    with pytest.raises(ValueError, match="smallest cut is 1"):
        cut(FAMED, 0)


@pytest.mark.parametrize("k", range(1, 9))
def test_every_cut_is_a_subset_of_every_bigger_one(k):
    # The property TaxoQuiz measured on sitelink thresholds: cutting a cut is
    # cutting the whole.
    for m in range(k, 9):
        assert cut(cut(FAMED, m), k) == cut(FAMED, k)


def test_entry_ranks_say_which_cut_first_holds_a_node():
    ranks = entry_ranks(FAMED)
    for k in range(1, 9):
        assert set(names(cut(FAMED, k))) == {x for x, r in ranks.items() if r <= k}


def test_tiers_follow_the_stops_and_end_at_the_leaf_count():
    t = tiers(FAMED, [2, 4, 6])
    assert t["root"] == t["a"] == t["b"] == t["lone"] == 2
    assert t["mid"] == t["c"] == t["d"] == 4
    assert t["dim"] == t["x"] == t["e"] == 6
    assert t["y"] == t["z"] == 8


def test_sizes_from_a_manifest():
    assert Sizes.from_manifest(None) is None
    assert Sizes.from_manifest(SIZES) == Sizes(2, 4, (2, 4, 6))
    assert Sizes.from_manifest({"min": 2, "default": 4}).stops == (2, 4)


@pytest.mark.parametrize("spec, why", [
    ({"min": 2}, "integer min and default"),
    ({"min": 2, "default": 3, "stops": [2, 4]}, "not one of the stops"),
    ({"min": 2, "default": 4, "stops": [2, 4, 4]}, "rise strictly"),
    ({"min": 3, "default": 4, "stops": [2, 4]}, "first stop"),
    ({"min": 1, "default": 1, "stops": [1]}, "at least 2"),
    ({"min": 2, "default": 4, "stops": [2, "4"]}, "integers"),
])
def test_sizes_that_make_no_sense_are_refused(spec, why):
    with pytest.raises(ValueError, match=why):
        Sizes.from_manifest(spec)


def sized(tree=FAMED, **manifest):
    return dataset.from_tree(tree, {"title": "Famed", "sizes": SIZES, **manifest}, "famed")


def test_the_validator_passes_a_sized_tree():
    report = validate(sized())
    assert report.ok, report.render()
    assert any("sizes: 2, 4, 6 and 8, daily at 4" in x for x in report.notes)


def test_the_validator_wants_fame_on_every_leaf_of_a_sized_tree():
    tree = n("root", None, f("a", 1), n("b"), f("c", 2))
    report = validate(sized(tree, sizes={"min": 2, "default": 2}))
    assert any("1 leaves have no fame" in x for x in report.failures)


def test_the_validator_refuses_bad_fame_anywhere():
    tree = n("root", None, f("a", -1), f("b", 1.5), n("g", None, f("c", 1), fame=3))
    fails = validate(dataset.from_tree(tree)).failures
    assert sum("not a non-negative integer" in x for x in fails) == 2
    assert any("'g' has a fame but is not a leaf" in x for x in fails)


def test_the_validator_wants_the_last_stop_below_the_whole_tree():
    report = validate(sized(sizes={"min": 2, "default": 4, "stops": [2, 4, 8]}))
    assert any("the last stop, 8" in x for x in report.failures)


def test_the_validator_checks_orderings_at_every_stop():
    # Without a ladder warmth comes from the paths below, so a cut can reorder
    # what the whole tree has right: a and c meet at mid, which at the whole
    # tree is warmer than root; at 2 neither c nor its cousins are there.
    chain = {"closer": [{"to": "c", "order": ["d", "a", "b"]}]}
    assert validate(sized(checks=chain)).ok
    bad = {"closer": [{"to": "c", "order": ["b", "d"]}]}
    fails = validate(sized(checks=bad)).failures
    assert fails and all(x.startswith(("c vs", "at 4:", "at 6:")) for x in fails)
    assert any(x.startswith("at 4:") for x in fails)


def test_a_bad_sizes_spec_fails_validation_rather_than_raising():
    report = validate(sized(sizes={"min": 2, "default": 5, "stops": [2, 4]}))
    assert any("not one of the stops" in x for x in report.failures)


def test_at_size_is_one_object_per_size_and_the_whole_is_itself():
    ds = sized()
    assert ds.at_size(4) is ds.at_size(4)
    assert ds.at_size(8) is ds and ds.at_size(50) is ds
    small = ds.at_size(2)
    assert small.id == ds.id and small.manifest is ds.manifest
    assert [label_of(x) for x in leaves(small.tree)] == ["a", "b"]


def test_a_seed_from_another_size_is_refused():
    ds = sized()
    _, at4 = game.pick(ds.at_size(4))
    with pytest.raises(ValueError, match="different dataset"):
        game.pick(ds.at_size(6), seed=at4)
    with pytest.raises(ValueError, match="different dataset"):
        game.pick(ds, seed=at4)
    assert game.pick(ds.at_size(4), seed=at4)[1] == at4


def test_every_game_plays_on_the_cut_tree():
    # A binary tree five deep, fame scattered, so a cut keeps leaves all over.
    def grow(path: str, depth: int) -> dict:
        if depth == 0:
            return f(f"leaf {path}", int(path, 2) * 37 % 32)
        return n(f"node {path}", None, grow(path + "0", depth - 1), grow(path + "1", depth - 1))
    tree = grow("1", 5)
    big = dataset.from_tree(tree, {"title": "Big", "sizes": {"min": 8, "default": 16}}, "big")
    small = big.at_size(16)
    kept = {label_of(x) for x in leaves(small.tree)}
    assert len(kept) == 16
    secret, s = game.pick(small)
    assert secret in kept
    state = game.get_game_state(small, secret, [sorted(kept)[0]], 1)
    assert {x["label"] for x in all_nodes(state) if x["node_type"] == "guess"} <= kept
    assert set(game.suggest(small, "leaf", 100)) <= kept
    for p in odd.make_set(small, odd.pick_seed(small)):
        assert set(p["choices"]) <= kept
    for p in lineup.make_set(small, lineup.pick_seed(small)):
        assert {p["target"], *p["choices"]} <= kept
    assert explore.stats(small)["leaves"] == 16
    # Warmth is the cut tree's: the root is 0 and the leaves 1 in both.
    w = warmth_by_name(small.tree, small.ladder)
    assert w["node 1"] == 0 and all(w[x["name"]] == 1 for x in leaves(small.tree))


def test_a_sized_trees_info_tiers_are_read_together(datasets_dir):
    d = datasets_dir("famed", FAMED, {"title": "Famed", "sizes": SIZES})
    (d / "info-2.json").write_text(json.dumps({"a": {"description": "first"}}))
    (d / "info-8.json").write_text(json.dumps({"z": {"description": "last"}}))
    (d / "info-notes.json").write_text("not json")
    assert dataset.load("famed").info == {"a": {"description": "first"}, "z": {"description": "last"}}


def test_the_cli_plays_at_a_size(datasets_dir, capsys):
    datasets_dir("famed", FAMED, {"title": "Famed", "sizes": SIZES})
    assert cli.main(["explore", "famed", "--size", "2"]) == 0
    out = capsys.readouterr().out
    assert "a  (1)" in out and "c  (1)" not in out
    assert cli.main(["explore", "famed"]) == 0   # the default size, 4
    assert "c  (1)" in capsys.readouterr().out
    datasets_dir("plain", FAMED, {"title": "Plain"})
    assert cli.main(["explore", "plain", "--size", "2"]) == 1
    assert "played whole" in capsys.readouterr().err


def test_the_cli_daily_is_at_the_default_size(datasets_dir, monkeypatch, capsys):
    datasets_dir("famed", FAMED, {"title": "Famed", "sizes": SIZES})
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["play", "famed", "--daily", "--size", "6"]) == 0
    tag = capsys.readouterr().out.split("Seed ")[1][:4]
    assert tag == seed.fingerprint(leaves(dataset.load("famed").at_size(4).tree))


def test_the_share_of_rank_claims_rejected_is_judged_on_the_whole_tree_only():
    # A bad claim high up (a "genus" above a class) among sixty good ones:
    # 2 in 62 for the whole tree, but a cut to the famous leaves keeps the bad
    # claim and drops most good ones. The data's rot is the whole tree's.
    ladder = {"levels": {"kingdom": 0, "class": 2, "genus": 5, "species": 6}, "top": 6}
    good = [n(f"G{i}", "genus", n(f"g{i}", "species", fame=1)) for i in range(60)]
    bad = n("X", "genus", n("C", "class", n("famous", "species", fame=100), n("known", "species", fame=90)))
    tree = n("root", "kingdom", bad, *good)
    ds = dataset.from_tree(tree, {"title": "T", "ladder": ladder, "sizes": {"min": 2, "default": 2}}, "t")
    report = validate(ds)
    assert report.ok, report.render()
    assert any("rejected by the tree: 2 of 62" in x for x in report.notes)
