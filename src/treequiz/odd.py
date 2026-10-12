"""Odd one out: three leaves, two of which share a group the third is not in.

A rooted tree answers "which two of these three are closest?" either exactly
or not at all. Either one pair's lowest common ancestor sits strictly below
the other two pairs' — which then coincide, at the node where all three
meet — or all three pairs meet at the same node and no pair is closer. A
puzzle is a triple of the first kind, and the odd one out is the leaf outside
the closer pair. Nothing else decides it: no rank, no warmth, no judgement
about what "related" means, so a tree with no ladder plays as well as one
with.

Puzzles are built from the top down, so every one is resolved by
construction: a **meeting node** (where all three meet), one of its children
to draw the pair from, another to draw the odd one from. The pair's own LCA
is wherever below that child the two happen to part.

**Difficulty is the meeting node's warmth.** Three leaves that share only the
root are easy (two cities in Europe and one in Asia); three that share a
country are hard. The tree's meeting nodes are ranked by warmth and cut into
thirds, and a set of ten runs easy to hard: three, four, three. Thirds of the
ranking rather than of the warmth scale, so every tree has hard puzzles,
however its warmth is spread.

**A meeting node is drawn in proportion to the leaves below it.** Drawn
evenly, the languages' small families counted as much as Indo-European, and
an "easy" puzzle was Chechen, Ingush and Rutulian. Weighted, big groups come
up as often as their share of the tree, which is how often a random leaf
would be in one.

**A set is its seed.** Every choice is a hash of the seed's body, the puzzle's
number, an attempt count and what is being chosen (`seed.draw`), so both
engines deal the same set from the same seed, and a link to a set is the
whole set. A puzzle that would show a leaf already shown in the set is drawn
again; after `MAX_ATTEMPTS` the repeat stands, which only a tree with too few
leaves for ten distinct puzzles reaches.
"""
from __future__ import annotations

from collections import namedtuple

from . import seed as seeds
from .dataset import Dataset
from .game import index as game_index
from .game import utc_today
from .tree import children_of, label_of

SET_SIZE = 10
# Which third of the ranking each puzzle of a set draws its meeting node from.
TIER_OF = (0, 0, 0, 1, 1, 1, 1, 2, 2, 2)
MAX_ATTEMPTS = 50
# Ways to show three things, so the odd one's position is drawn too.
ORDERS = ((0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0))

# A node where three leaves can meet: its children's leaves, as lists, in tree
# order. Eligible when it has two children and one of them holds two leaves.
_Meeting = namedtuple("_Meeting", "node warmth kids size")
_cache: dict[int, tuple[dict, list[list[_Meeting]]]] = {}


def tiers(ds: Dataset) -> list[list[_Meeting]]:
    """The tree's meeting nodes by warmth, coolest first, in three tiers.

    Ties in warmth keep tree order, so the ranking is the same in both engines.
    A tier is empty only on a tree with fewer than three meeting nodes; a draw
    from an empty tier falls back to all of them."""
    cached = _cache.get(id(ds.tree))
    if cached is not None and cached[0] is ds.tree:
        return cached[1]
    warmth = game_index(ds).warmth
    points: list[_Meeting] = []

    def walk(node: dict) -> list[dict]:
        kids = children_of(node)
        if not kids:
            return [node]
        under = [walk(c) for c in kids]
        if len(under) >= 2 and any(len(u) >= 2 for u in under):
            points.append(_Meeting(node, warmth[node["name"]], under, sum(len(u) for u in under)))
        return [leaf for u in under for leaf in u]

    walk(ds.tree)
    # `walk` appends children before parents; preorder is what "tree order" means.
    preorder = {n["name"]: i for i, n in enumerate(_preorder(ds.tree))}
    points.sort(key=lambda m: (m.warmth, preorder[m.node["name"]]))
    n = len(points)
    out = [points[t * n // 3:(t + 1) * n // 3] for t in range(3)]
    _cache[id(ds.tree)] = (ds.tree, out)
    return out


def clear_cache() -> None:
    _cache.clear()


def _preorder(tree: dict) -> list[dict]:
    out: list[dict] = []
    stack = [tree]
    while stack:
        node = stack.pop()
        out.append(node)
        stack.extend(reversed(children_of(node)))
    return out


def _weighted(pool: list[_Meeting], r: int) -> _Meeting:
    """The meeting node `r` lands in, laying the pool end to end by size."""
    for m in pool:
        if r < m.size:
            return m
        r -= m.size
    raise AssertionError("r is drawn below the pool's total size")


def _group(node: dict, warmth: float) -> dict:
    return {"name": node["name"], "label": label_of(node), "rank": node.get("rank", ""), "warmth": warmth}


def _lca(a: list[dict], b: list[dict]) -> dict:
    result = a[0]
    for x, y in zip(a, b):
        if x["name"] != y["name"]:
            break
        result = x
    return result


def puzzle(ds: Dataset, body: str, i: int, used: set[str]) -> dict:
    """The `i`th puzzle of the set `body` names, avoiding the leaves in `used`."""
    tiered = tiers(ds)
    pool = tiered[TIER_OF[i % SET_SIZE]] or [m for t in tiered for m in t]
    if not pool:
        raise ValueError("No three of this tree's leaves have two closer than the third.")
    for attempt in range(MAX_ATTEMPTS):
        key = f"treequiz-odd:{body}:{i}:{attempt}"
        meet = _weighted(pool, seeds.draw(f"{key}:meet", sum(m.size for m in pool)))
        pairable = [k for k, u in enumerate(meet.kids) if len(u) >= 2]
        k1 = pairable[seeds.draw(f"{key}:pair", len(pairable))]
        others = [k for k in range(len(meet.kids)) if k != k1]
        k2 = others[seeds.draw(f"{key}:odd", len(others))]
        under = meet.kids[k1]
        ia = seeds.draw(f"{key}:a", len(under))
        ib = seeds.draw(f"{key}:b", len(under) - 1)
        if ib >= ia:
            ib += 1
        a, b = under[ia], under[ib]
        c = meet.kids[k2][seeds.draw(f"{key}:c", len(meet.kids[k2]))]
        if not {a["name"], b["name"], c["name"]} & used:
            break
    trio = (a, b, c)
    order = ORDERS[seeds.draw(f"{key}:order", len(ORDERS))]
    idx = game_index(ds)
    pair = _lca(idx.lineage_of[label_of(a)], idx.lineage_of[label_of(b)])
    return {
        "choices": [label_of(trio[k]) for k in order],
        "odd": label_of(c),
        "pair": [label_of(a), label_of(b)],
        "group": _group(pair, idx.warmth[pair["name"]]),
        "shared": _group(meet.node, meet.warmth),
        "tier": TIER_OF[i % SET_SIZE],
    }


def make_set(ds: Dataset, seed: str) -> list[dict]:
    """The ten puzzles a seed names. Raises ValueError for a seed from another
    tree, or a tree with no puzzle in it."""
    body = seeds.body_of(seed, game_index(ds).leaves)
    used: set[str] = set()
    out = []
    for i in range(SET_SIZE):
        p = puzzle(ds, body, i, used)
        used.update(_names(ds, p))
        out.append(p)
    return out


def _names(ds: Dataset, p: dict) -> list[str]:
    by_label = game_index(ds).by_label
    return [by_label[label]["name"] for label in p["choices"]]


def pick_seed(ds: Dataset, daily: bool = False, today=None) -> str:
    """A new set's seed: random, or the day's."""
    return seeds.make_seed(game_index(ds).leaves, day=(today or utc_today()) if daily else None)


def check(p: dict, choice: str) -> bool:
    return choice == p["odd"]
