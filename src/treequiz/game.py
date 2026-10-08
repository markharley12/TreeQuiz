"""The guessing game: pick a secret leaf, and draw what the guesses reveal.

TaxoQuiz's `game_state.py`, `pick_animal.py` and `list_animals.py` in one
module, with "species" and "common name" replaced by "leaf" and "label". The
rules are the same:

- A guess's score is the warmth of its lowest common ancestor with the secret.
- The display tree is the union of the guesses' lineages, pruned to them.
- A `???` node marks the child of the deepest LCA reached on the secret's
  lineage: it reveals the branch, never the depth. It takes its parent's warmth,
  not its own — its own would usually be a leaf's 1.0, painting it greener than
  any real guess and saying "the answer is one step below this".
- A hint shows one more *node* of the secret's lineage past the deepest reached,
  and never the secret itself; `can_hint` on the marker goes false when the
  next node would be the answer.
- `get_game_state(secret, [])` with no hints is None: the union of no lineages
  prunes the root away. Kept from TaxoQuiz as a pinned rough edge; the frontend
  never asks.
"""
from __future__ import annotations

import re
from collections import namedtuple
from datetime import date, datetime, timezone

from . import seed as seeds
from .dataset import Dataset
from .ladder import warmth_by_name
from .tree import children_of, label_of, leaves

_Index = namedtuple("_Index", "leaves by_label lineage_of depth_of warmth")
# Keyed by id() of the tree, holding the tree itself beside the index: while it
# is held its id cannot be reused by another object, so a hit is always the
# same tree. Trees are never mutated, so an index never goes stale.
_indexes: dict[int, tuple[dict, _Index]] = {}


def index(ds: Dataset) -> _Index:
    """Per-tree lookups, built once."""
    cached = _indexes.get(id(ds.tree))
    if cached is not None and cached[0] is ds.tree:
        return cached[1]
    by_label: dict[str, dict] = {}
    lineage_of: dict[str, list[dict]] = {}
    depth_of: dict[str, int] = {}

    def walk(node: dict, path: list[dict], depth: int) -> None:
        depth_of[node["name"]] = depth
        kids = children_of(node)
        if not kids:
            label = label_of(node)
            by_label[label] = node
            lineage_of[label] = path + [node]
        for child in kids:
            walk(child, path + [node], depth + 1)

    walk(ds.tree, [], 0)
    idx = _Index(leaves(ds.tree), by_label, lineage_of, depth_of, warmth_by_name(ds.tree, ds.ladder))
    _indexes[id(ds.tree)] = (ds.tree, idx)
    return idx


def clear_cache() -> None:
    _indexes.clear()


def _lca(lin_a: list[dict], lin_b: list[dict]) -> dict:
    """The deepest node both lineages share."""
    result = lin_a[0]
    for a, b in zip(lin_a, lin_b):
        if a["name"] != b["name"]:
            break
        result = a
    return result


def get_game_state(ds: Dataset, secret: str, guesses: list[str], hints: int = 0) -> dict | None:
    """The annotated display tree for a round. Names are leaf labels.

    Raises ValueError for a secret or guess the dataset does not hold.
    """
    idx = index(ds)
    for name in [secret, *guesses]:
        if name not in idx.by_label:
            raise ValueError(f"Not in this dataset: {name!r}")

    secret_lineage = idx.lineage_of[secret]
    secret_names = {n["name"] for n in secret_lineage}
    guess_lineages = [idx.lineage_of[g] for g in guesses]
    guess_names = {idx.by_label[g]["name"] for g in guesses}

    lca_depth: dict[str, int] = {}
    lca_warmth: dict[str, float] = {}
    for g, lin in zip(guesses, guess_lineages):
        shared = _lca(secret_lineage, lin)
        name = idx.by_label[g]["name"]
        lca_depth[name] = idx.depth_of[shared["name"]]
        lca_warmth[name] = idx.warmth[shared["name"]]

    show = {n["name"] for lin in guess_lineages for n in lin}

    marker: str | None = None
    can_hint = False
    if guess_lineages or hints > 0:
        # The root is on every lineage, so it is where hints start with no guess.
        deepest_depth = 0
        deepest_idx = 0
        for lin in guess_lineages:
            shared = _lca(secret_lineage, lin)
            d = idx.depth_of[shared["name"]]
            if d > deepest_depth:
                deepest_depth = d
                deepest_idx = next(i for i, n in enumerate(secret_lineage) if n["name"] == shared["name"])
        last = len(secret_lineage) - 1
        if deepest_idx < last:
            known = min(deepest_idx + max(hints, 0), last - 1)
            show.update(n["name"] for n in secret_lineage[:known + 1])
            marker = secret_lineage[known + 1]["name"]
            show.add(marker)
            can_hint = known + 1 < last

    def prune(node: dict, parent_warmth: float) -> dict | None:
        name = node["name"]
        if name not in show:
            return None
        kind = "secret" if name == marker else "guess" if name in guess_names else "ancestor"
        own = parent_warmth if kind == "secret" else idx.warmth[name]
        kids = []
        for child in children_of(node):
            pruned = prune(child, own)
            if pruned is not None:
                kids.append(pruned)
        out = {
            # None on ??? simply because there is nothing there to look up,
            # which also keeps it unclickable. Not a secrecy measure: the app
            # holds the answer to check a win without asking anyone.
            "name": None if kind == "secret" else name,
            "label": "???" if kind == "secret" else label_of(node),
            # Blank on ???, whose rank would say how far below the answer sits.
            "rank": "" if kind == "secret" else node.get("rank", ""),
            "node_type": kind,
            "depth": idx.depth_of[name],
            "warmth": own,
            "on_secret_path": name in secret_names,
            "children": kids,
        }
        if kind == "guess":
            out["lca_depth"] = lca_depth.get(name, 0)
            out["lca_warmth"] = lca_warmth.get(name, 0.0)
        if kind == "secret":
            out["can_hint"] = can_hint
        return out

    return prune(ds.tree, 0.0)


def utc_today() -> date:
    """The daily's date, in UTC on both engines, so it is one round at one
    instant everywhere."""
    return datetime.now(timezone.utc).date()


def pick(ds: Dataset, seed: str | None = None, daily: bool = False, today: date | None = None) -> tuple[str, str]:
    """The secret leaf's label, and the seed that names it."""
    lv = index(ds).leaves
    if seed:
        return label_of(seeds.resolve(seed, lv)), seeds.normalise(seed)
    full = seeds.make_seed(lv, day=(today or utc_today()) if daily else None)
    return label_of(seeds.resolve(full, lv)), full


_WORD = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")
_DISAMBIGUATION = re.compile(r"[ ]*(\([^)]*\))?[ ]*(#[0-9]+)?$")
TIERS = 5


def match_tier(name: str, needle: str) -> int | None:
    """How well a name matches a lower-cased query, or None for no match.

    0 exact; 1 the name's last word ("snail" in "garden snail"); 2 a whole word
    elsewhere; 3 the start of a word; 4 anywhere. The last word is its own tier
    because a name tends to end in what the thing *is* — a garden snail is a
    snail, a snail eater is a snake — and a trailing " (qualifier)" or " #2"
    does not count as a word. Word characters are spelled out as ASCII rather
    than left to `\\b`, because Python's and JavaScript's disagree.
    """
    low = name.lower()
    if low == needle:
        return 0
    if not needle:
        return 4
    core_end = len(_DISAMBIGUATION.sub("", low, count=1))
    best = None
    i = low.find(needle)
    while i != -1:
        j = i + len(needle)
        before = i == 0 or low[i - 1] not in _WORD
        after = j == len(low) or low[j] not in _WORD
        if before and after:
            tier = 1 if j == core_end else 2
        else:
            tier = 3 if before else 4
        best = tier if best is None else min(best, tier)
        i = low.find(needle, i + 1)
    return best


def suggest(ds: Dataset, query: str, limit: int = 50, exclude: set[str] | list[str] | None = None) -> list[str]:
    """Up to `limit` leaf labels matching `query`, best first.

    Ranked by `match_tier` on the label; a leaf whose label does not match but
    one of whose aliases does comes after every label match, ranked the same
    way among themselves. Tree order within a tier keeps relatives together.
    """
    needle = query.lower()
    skip = set(exclude or ())
    tiers: list[list[str]] = [[] for _ in range(TIERS * 2)]
    for leaf in index(ds).leaves:
        label = label_of(leaf)
        if label in skip:
            continue
        tier = match_tier(label, needle)
        if tier is None:
            alias_tiers = [t for t in (match_tier(a, needle) for a in leaf.get("aliases") or []) if t is not None]
            if alias_tiers:
                tier = TIERS + min(alias_tiers)
        if tier is not None:
            tiers[tier].append(label)
    return [label for tier in tiers for label in tier][:limit]
