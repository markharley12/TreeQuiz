"""The round: state, the ??? marker, hints, picking, and suggestions."""
from __future__ import annotations

from datetime import date

import pytest

from treequiz import game, seed


def nodes(state):
    yield state
    for c in state["children"]:
        yield from nodes(c)


def by_label(state):
    return {s["label"]: s for s in nodes(state)}


def test_a_guess_is_scored_by_its_lca_with_the_secret(zoo):
    state = game.get_game_state(zoo, "lion", ["tiger", "grey wolf", "moon jelly"])
    got = by_label(state)
    assert got["tiger"]["lca_warmth"] == 5 / 6      # same genus
    assert got["grey wolf"]["lca_warmth"] == 3 / 6  # same order
    assert got["moon jelly"]["lca_warmth"] == 0.0   # only the root
    assert got["tiger"]["name"] == "Panthera tigris"


def test_the_marker_shows_the_branch_and_takes_its_parents_warmth(zoo):
    state = game.get_game_state(zoo, "lion", ["domestic cat"])
    marker = by_label(state)["???"]
    assert marker["name"] is None and marker["rank"] == ""
    # The marker is Panthera, under Felidae: coloured as Felidae, not as a genus.
    felidae = by_label(state)["Felidae"]
    assert [c["label"] for c in felidae["children"]].count("???") == 1
    assert marker["warmth"] == felidae["warmth"]
    assert marker["can_hint"] is True


def test_a_win_has_no_marker(zoo):
    state = game.get_game_state(zoo, "lion", ["tiger", "lion"])
    assert "???" not in by_label(state)
    assert by_label(state)["lion"]["lca_warmth"] == 1.0


def test_hints_walk_down_the_secrets_lineage_and_stop_short_of_it(zoo):
    labels = lambda h: set(by_label(game.get_game_state(zoo, "lion", [], hints=h)))  # noqa: E731
    # One node past the deepest reached, which with no guesses is the root.
    assert labels(1) == {"Animalia", "Chordata", "???"}
    assert "Mammalia" in labels(2)
    deepest = game.get_game_state(zoo, "lion", [], hints=50)
    marker = by_label(deepest)["???"]
    assert "Panthera" in by_label(deepest) and marker["can_hint"] is False
    assert "lion" not in by_label(deepest)


def test_no_guesses_and_no_hints_is_none(zoo):
    # Pinned rough edge: the union of no lineages prunes the root away.
    assert game.get_game_state(zoo, "lion", []) is None


def test_unknown_names_raise_and_say_which(zoo):
    with pytest.raises(ValueError, match="'Lion'"):
        game.get_game_state(zoo, "lion", ["Lion"])


def test_pick_is_reproducible_from_its_seed(zoo):
    secret, s = game.pick(zoo)
    assert game.pick(zoo, seed=s) == (secret, s)
    assert game.pick(zoo, seed=s.lower().replace("-", " ")) == (secret, s)


def test_the_daily_depends_only_on_the_date(zoo):
    day = date(2026, 10, 8)
    a = game.pick(zoo, daily=True, today=day)
    assert a == game.pick(zoo, daily=True, today=day)
    assert a[1].endswith(seed.body_for_date(day))


def test_suggestions_rank_whole_words_before_fragments(zoo):
    # "cat" is the last word of "domestic cat"; nothing else contains it.
    assert game.suggest(zoo, "cat") == ["domestic cat"]
    assert game.suggest(zoo, "o")[:1] == ["lion"]  # tier 4, tree order


def test_suggestions_match_aliases_after_labels(zoo):
    assert game.suggest(zoo, "panthera leo") == ["lion"]
    assert game.suggest(zoo, "leo") == ["leopard", "lion"]  # label prefix, then alias word


def test_suggestions_skip_what_is_already_guessed(zoo):
    assert game.suggest(zoo, "", exclude={"lion"})[0] == "tiger"


@pytest.mark.parametrize("name,needle,tier", [
    ("garden snail", "garden snail", 0),
    ("garden snail", "snail", 1),
    ("snail eater", "snail", 2),
    ("crowned eagle", "crow", 3),
    ("scrows", "crow", 4),
    ("lion (Panthera leo)", "lion", 1),
    ("lion #2", "lion", 1),
    ("lion", "x", None),
])
def test_match_tier(name, needle, tier):
    assert game.match_tier(name, needle) == tier
