"""The terminal front end: listing, validating, and a round played on stdin."""
from __future__ import annotations

import io
import json

from conftest import ZOO, ZOO_LADDER

from treequiz import cli, dataset, game


def test_list_and_validate_every_dataset(capsys):
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "maths" in out and "animals" in out
    assert cli.main(["validate", "--all"]) == 0
    assert "FAIL" not in capsys.readouterr().out


def test_state_prints_the_engines_json(capsys):
    assert cli.main(["state", "animals", "lion", "tiger"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["label"] == "Animalia"


def test_an_unknown_name_is_an_error_not_a_traceback(capsys):
    assert cli.main(["state", "animals", "lion", "unicorn"]) == 1
    assert "unicorn" in capsys.readouterr().err


def test_a_round_on_stdin(datasets_dir, monkeypatch, capsys):
    datasets_dir("zoo", ZOO, {"title": "Zoo", "noun": "animal", "ladder": ZOO_LADDER})
    secret, s = game.pick(dataset.load("zoo"))
    monkeypatch.setattr("sys.stdin", io.StringIO(f"o\n?\n{secret}\n"))
    assert cli.main(["play", "zoo", "--seed", s]) == 0
    out = capsys.readouterr().out
    assert "You got it in 1 with 1 hints" in out
    assert "???" in out   # the hint drew the marker


def test_a_line_up_on_stdin_scores_each_order(datasets_dir, monkeypatch, capsys):
    from treequiz import lineup
    datasets_dir("zoo", ZOO, {"title": "Zoo", "noun": "animal", "ladder": ZOO_LADDER})
    ds = dataset.load("zoo")
    s = lineup.pick_seed(ds)
    puzzles = lineup.make_set(ds, s)
    # The first in the right order, typed after a malformed try; the rest
    # in the order shown.
    right = "".join(str(puzzles[0]["choices"].index(o) + 1) for o in puzzles[0]["order"])
    monkeypatch.setattr("sys.stdin", io.StringIO("12\n" + right + "\n" + "1234\n" * 4))
    assert cli.main(["lineup", "zoo", "--seed", s]) == 0
    out = capsys.readouterr().out
    assert "4 of 4 in place" in out
    total = 4 + sum(lineup.score(p, p["choices"]) for p in puzzles[1:])
    assert f"{total} of 20." in out
