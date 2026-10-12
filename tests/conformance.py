"""Cases the TypeScript engine must answer exactly as Python does.

The engine exists twice — here, and in `frontend/src/engine/`, which is what
lets the app run with no server. Two copies of a rule drift unless something
holds them together, so this writes Python's answers to a fixed set of
questions into `frontend/src/engine/conformance.json`, and both suites check:

- `tests/test_conformance.py` fails while the file is stale, so a Python change
  cannot land without regenerating it;
- `frontend/src/engine/conformance.test.ts` fails while TypeScript disagrees,
  so the regenerated file cannot land without the matching port.

Regenerate after changing any game, explore, ladder or seed logic, or any
shipped dataset:

    .venv/bin/python tests/conformance.py

Numbers are compared exactly. Both sides do the same IEEE operations in the
same order, so any difference is a real divergence.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import n  # noqa: E402

from treequiz import dataset, explore, game, odd, seed  # noqa: E402
from treequiz.dataset import Ladder  # noqa: E402
from treequiz.ladder import believed_levels, warmth_by_name  # noqa: E402
from treequiz.tree import all_nodes, label_of, leaves  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[1] / "frontend" / "src" / "engine" / "conformance.json"

LINNAEAN = {"levels": {"life": -1, "kingdom": 0, "subkingdom": 0.3, "phylum": 1, "class": 2,
                       "subclass": 2.3, "order": 3, "family": 4, "genus": 5, "species": 6}, "top": 6}

# Trees for the branches of the ladder logic the shipped data does not reach.
SYNTHETIC: list[tuple[dict | None, dict]] = [
    # A contradiction up the tree, and a rank above the root's.
    (LINNAEAN, n("Animalia", "kingdom",
                 n("Chordata", "phylum",
                   n("Tetrapodomorpha", "subclass",
                     n("Mammalia", "class", n("Theria", None, n("Carnivora", "order",
                       n("Felidae", "family", n("Panthera", "genus", n("Panthera leo", "species"))))))),
                   n("Aves", "class", n("Passer domesticus", "species"))),
                 n("Eukaryota", "life", n("Odd", "species")))),
    # Ties, casing, whitespace, and prototype-shaped names and ranks.
    (LINNAEAN, n("Root", "Kingdom",
                 n("Eumetazoa", "subkingdom",
                   n("Bilateria", " SubKingdom ", n("constructor", "toString"), n("x", "genus")),
                   n("toString", "phylum", n("hasOwnProperty", "species"))))),
    # The crossing case the strict floor exists for.
    (LINNAEAN, n("Mammalia", "class",
                 n("A", "clade",
                   n("Near", "subclass", n("Near sp", "species")),
                   n("B", "clade", n("B1", "clade", n("B2", "clade", n("B3", "clade",
                     n("Far", "subclass", n("Far sp", "species"))))))))),
    # A child interpolated to exactly its parent's warmth: C is placed against
    # the genus ten steps down and lands on 2.5, which is where P sits against
    # the order beside it. Equal must count as not warmer, or the tie stands.
    (LINNAEAN, n("Root", "kingdom", n("C0", "class",
                 n("P", None, n("F", "order", n("f sp", "species")),
                   n("C", None, n("U1", None, n("U2", None, n("U3", None, n("U4", None, n("U5", None,
                     n("U6", None, n("U7", None, n("U8", None, n("U9", None,
                       n("G", "genus", n("g sp", "species")))))))))))))))),
    # No ladder at all; ties below broken toward the longer path.
    (None, n("root", None,
             n("a", None, n("near"), n("x", None, n("y", None, n("deep")))),
             n("b", None, n("b1", None, n("b1a"), n("b1b")), n("b2")),
             n("c"))),
    # A ladder with fractional, unordered keys and a root ranked mid-ladder.
    ({"levels": {"Area": 2, "Branch": 1, "Section": 3.5}, "top": 4},
     n("M", "Section", n("Br", "Branch", n("Ar", "Area", n("S1", "Section"), n("S2", "Section")),
                         n("Un", None, n("S3", None))), n("Ar2", "Area", n("S4")))),
]


def attempt(fn, *args, **kwargs) -> dict:
    """The answer, or the error message: both are behaviour the port must match."""
    try:
        return {"result": fn(*args, **kwargs)}
    except ValueError as e:
        return {"error": str(e)}


def sha256_cases() -> list:
    inputs = ["", "a", "abc", *("a" * k for k in (55, 56, 63, 64, 65, 119, 120)),
              "The quick brown fox " * 50, "é μ 🦁 ≠"]
    return [{"input": s, "digest": hashlib.sha256(s.encode()).hexdigest()} for s in inputs]


def ladder_cases() -> list:
    out = []
    for spec, tree in SYNTHETIC:
        lad = Ladder.from_manifest(spec)
        believed = believed_levels(tree, lad)
        out.append({
            "ladder": spec,
            "tree": tree,
            "believed": {x["name"]: believed[id(x)] for x in all_nodes(tree)},
            "warmth": warmth_by_name(tree, lad),
        })
    return out


# Trees for the odd-one-out rules no shipped tree reaches: no puzzle at all, too
# few leaves for ten different puzzles, and meeting nodes tied on warmth.
ODD_TREES = [
    n("root", None, n("a"), n("b"), n("c")),
    n("root", None, n("g", None, n("a"), n("b")), n("c")),
    n("root", None, n("p", None, n("p1", None, n("a"), n("b")), n("c")),
      n("q", None, n("q1", None, n("d"), n("e")), n("f")), n("h")),
]


def odd_cases() -> list:
    out = []
    for i, tree in enumerate(ODD_TREES):
        ds = dataset.from_tree(tree, {"title": f"odd{i}"}, f"odd{i}")
        s = f"{seed.fingerprint(leaves(tree))}-ABCDEF"
        out.append({"tree": tree, "seed": s, **attempt(odd.make_set, ds, s)})
    return out


def dataset_cases(ds: dataset.Dataset, rng: random.Random) -> dict:
    lv = leaves(ds.tree)
    labels = [label_of(x) for x in lv]
    fp = seed.fingerprint(lv)
    bodies = [seed._encode(hashlib.sha256(f"{ds.id}{i}".encode()).digest(), seed.BODY_LEN) for i in range(24)]

    # Every case is a whole game state or slice, so the file grows by a quarter
    # megabyte a dataset at these counts; they were cut once, in Oct 2026, to
    # the fewest that still reach every rule (the specials below stay).
    rounds = []
    for i in range(9):
        secret = rng.choice(labels)
        guesses = rng.sample(labels, rng.randint(1, 6))
        if i % 3 == 0:
            guesses.append(secret)
        rounds.append({"secret": secret, "guesses": guesses, "hints": i % 4})
    # Hints with no guesses; a near miss; unknown names, both sides.
    rounds += [
        {"secret": labels[0], "guesses": [], "hints": 2},
        {"secret": labels[1], "guesses": [labels[2]], "hints": 99},
        {"secret": labels[0], "guesses": [], "hints": 0},
        {"secret": labels[0], "guesses": ["definitely not here"], "hints": 0},
        {"secret": "nor this", "guesses": [labels[0]], "hints": 0},
    ]
    for r in rounds:
        r.update(attempt(game.get_game_state, ds, r["secret"], r["guesses"], r["hints"]))

    words = sorted({w for lab in labels for w in lab.lower().split()})
    queries = ["", "a", "e", "ar", "the", "on", "(", "#2", *rng.sample(words, 10),
               labels[3].lower(), labels[3][:4]]
    # The exclusion list is the first 40 labels, written once rather than into
    # every case that uses it.
    exclude = labels[:40]
    suggest = []
    for q in queries:
        for limit, excluding in ((50, False), (5, True)):
            suggest.append({"q": q, "limit": limit, "excluding": excluding,
                            "result": game.suggest(ds, q, limit, exclude if excluding else [])})

    names = [x["name"] for x in all_nodes(ds.tree)]
    internal = [x["name"] for x in all_nodes(ds.tree) if x.get("children")]
    roots = [None, *rng.sample(internal, 4), lv[5]["name"], "No such node"]
    subtrees = []
    for root in roots:
        # The large budget only from the top, where it is the app's first
        # screen; a depth of two only from below it, which is half the size
        # (cut with the lineages below, at nine trees: the depth-one case
        # from the top still runs the depth limit there).
        shapes = ((None, 200), (None, 40), (1, 7)) if root is None else ((None, 40), (2, None), (1, 7))
        for depth, budget in shapes:
            subtrees.append({"root": root, "depth": depth, "budget": budget,
                             **attempt(explore.subtree, ds, root, depth, budget)})
    # A budget met exactly by a level: stops at `>`, not `>=`.
    first = len(ds.tree.get("children") or [])
    subtrees.append({"root": None, "depth": None, "budget": 1 + first,
                     **attempt(explore.subtree, ds, None, None, 1 + first)})

    return {
        "id": ds.id,
        "warmth": warmth_by_name(ds.tree, ds.ladder),
        "seeds": {
            "fingerprint": fp,
            "resolve": [{"seed": s, **attempt(lambda s=s: label_of(seed.resolve(s, lv)))}
                        for s in [f"{fp}-{b}" for b in bodies] + [f" {fp.lower()} {bodies[0].lower()}", "0000-000000"]],
            "daily": [{"date": d.isoformat(), "secret": game.pick(ds, daily=True, today=d)[0]}
                      for d in (date(2026, 1, 1), date(2026, 10, 8), date(2027, 2, 28))],
        },
        "game": rounds,
        # One set covers every tier; a set is ten puzzles, so one is enough.
        "odd": [{"seed": s, **attempt(odd.make_set, ds, s)} for s in (f"{fp}-{bodies[1]}", "0000-000000")],
        "suggest_exclude": exclude,
        "suggest": suggest,
        "explore": {
            "subtree": subtrees,
            "lineage": [{"name": x, **attempt(explore.lineage, ds, x)}
                        for x in [rng.choice(names), "No such node"]],
            "search": [{"q": q, "limit": lim, "result": explore.search(ds, q, lim)}
                       for q in [*rng.sample(words, 6), "a", " e ", ""] for lim in (25, 3)],
            "stats": explore.stats(ds),
        },
    }


def build() -> dict:
    rng = random.Random(20261008)
    return {
        "sha256": sha256_cases(),
        "seeds": {
            "fingerprints": [{"labels": ls, "fingerprint": seed.fingerprint([{"name": x} for x in ls])}
                             for ls in ([], ["a"], ["lion", "tiger"], ["é🦁"])],
            "daily": [{"date": d, "body": seed.body_for_date(date.fromisoformat(d))}
                      for d in ("2026-01-01", "2026-10-08", "2030-12-31")],
            "normalise": [{"input": s, **attempt(seed.normalise, s)}
                          for s in ["abcd-234567", " AB CD 23 45 67 ", "ABCD234567", "ABCD-2345", "", "not a seed at all"]],
        },
        "ladder": ladder_cases(),
        "odd": odd_cases(),
        "datasets": [dataset_cases(dataset.load(i), rng) for i in dataset.available()],
    }


def render() -> str:
    return json.dumps(build(), ensure_ascii=False, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(render())
    print(f"wrote {GOLDEN} ({GOLDEN.stat().st_size // 1024} KB)")
