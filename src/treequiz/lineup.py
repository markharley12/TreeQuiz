"""Line-up: a leaf, and four others to put in order of kinship to it.

Each of the four meets the target at a different one of its ancestors, so the
order is the tree's alone: nearest is the one whose lowest common ancestor
with the target is deepest. As in odd one out, nothing else decides it — no
rank, no warmth — so a tree with no ladder plays as well as one with.

A puzzle is built from the target up. Its ancestors are the levels it can be
met at; four are drawn, and under each a leaf from a branch other than the
target's, which is a leaf that meets the target exactly there. An ancestor
with no other branch (a genus of one species, a root of one child) is no
level: nothing meets the target there that does not meet it lower down.

**Difficulty is how near the target the levels are.** Levels spread over the
whole lineage (the land plants, the flowering plants, the rose family, the
apples) are easy; levels packed just above the target (the rose family, a
subfamily, a tribe, the apples) are hard. The levels are drawn from a window
of the target's deepest levels — all of them, the deepest two thirds, or the
deepest third, never fewer than four — cut into four runs, one level from
each, so the four never bunch at one end of the window. A set of five runs
easy, easy, medium, medium, hard.

**A target needs four levels.** A tree where no leaf has four (a flat list
under a root) has no line-ups, and says so.

**A set is its seed**, drawn as odd one out's are: every choice is
`seed.draw` of the set's body, the puzzle's number, an attempt count and what
is chosen, so both engines deal the same set from the same seed. A puzzle
showing a leaf already in the set is drawn again; after `MAX_ATTEMPTS` the
repeat stands, which only a tree too small for five distinct puzzles reaches.
"""
from __future__ import annotations

from collections import namedtuple
from itertools import permutations

from . import seed as seeds
from .dataset import Dataset
from .game import index as game_index
from .game import utc_today
from .tree import children_of, label_of

SET_SIZE = 5
OPTIONS = 4
# Which window each puzzle of a set draws its levels from: see `window`.
TIER_OF = (0, 0, 1, 1, 2)
MAX_ATTEMPTS = 50
# Ways to show four things, in lexicographic order (the port lists the same).
PERMUTATIONS = tuple(permutations(range(OPTIONS)))

# `span` is each node's leaves as a run of the tree's leaves, [start, end), so
# "under this node but not under that child" is two runs, not a list.
# `eligible` is the leaves with at least OPTIONS levels, in tree order.
_Shape = namedtuple("_Shape", "span eligible")
_cache: dict[int, tuple[dict, _Shape]] = {}


def shape(ds: Dataset) -> _Shape:
    cached = _cache.get(id(ds.tree))
    if cached is not None and cached[0] is ds.tree:
        return cached[1]
    span: dict[str, tuple[int, int]] = {}
    count = 0

    def walk(node: dict) -> None:
        nonlocal count
        start = count
        kids = children_of(node)
        if not kids:
            count += 1
        for child in kids:
            walk(child)
        span[node["name"]] = (start, count)

    walk(ds.tree)
    idx = game_index(ds)
    out = _Shape(span, [leaf for leaf in idx.leaves
                        if len(_levels(idx.lineage_of[label_of(leaf)], span)) >= OPTIONS])
    _cache[id(ds.tree)] = (ds.tree, out)
    return out


def clear_cache() -> None:
    _cache.clear()


def _size(span: dict[str, tuple[int, int]], node: dict) -> int:
    start, end = span[node["name"]]
    return end - start


def _levels(lineage: list[dict], span: dict[str, tuple[int, int]]) -> list[int]:
    """Where in `lineage` (root first, the leaf last) something else can meet
    the leaf: every ancestor with a branch besides the one the leaf is on."""
    return [d for d in range(len(lineage) - 1) if _size(span, lineage[d]) > _size(span, lineage[d + 1])]


def window(m: int, tier: int) -> int:
    """How many of a target's `m` levels, the deepest, a tier draws from."""
    return max(OPTIONS, (m, (2 * m + 2) // 3, (m + 2) // 3)[tier])


def _group(node: dict, warmth: float) -> dict:
    return {"name": node["name"], "label": label_of(node), "rank": node.get("rank", ""), "warmth": warmth}


def puzzle(ds: Dataset, body: str, i: int, used: set[str]) -> dict:
    """The `i`th puzzle of the set `body` names, avoiding the leaves in `used`."""
    span, eligible = shape(ds)
    if not eligible:
        raise ValueError(f"No leaf of this tree has {OPTIONS} levels to meet others at.")
    idx = game_index(ds)
    leaves = idx.leaves
    tier = TIER_OF[i % SET_SIZE]
    for attempt in range(MAX_ATTEMPTS):
        key = f"treequiz-lineup:{body}:{i}:{attempt}"
        target = eligible[seeds.draw(f"{key}:target", len(eligible))]
        lineage = idx.lineage_of[label_of(target)]
        levels = _levels(lineage, span)
        w = window(len(levels), tier)
        deepest = levels[len(levels) - w:]
        chosen: list[int] = []       # depths in the lineage, root first
        for k in range(OPTIONS):
            lo, hi = k * w // OPTIONS, (k + 1) * w // OPTIONS
            chosen.append(deepest[lo + seeds.draw(f"{key}:level{k}", hi - lo)])
        options = []
        for k, d in enumerate(chosen):
            (a0, a1), (p0, p1) = span[lineage[d]["name"]], span[lineage[d + 1]["name"]]
            r = seeds.draw(f"{key}:leaf{k}", (a1 - a0) - (p1 - p0))
            options.append(leaves[a0 + r] if r < p0 - a0 else leaves[p1 + r - (p0 - a0)])
        if not {target["name"], *(o["name"] for o in options)} & used:
            break
    nearest = options[::-1]
    order = PERMUTATIONS[seeds.draw(f"{key}:order", len(PERMUTATIONS))]
    return {
        "target": label_of(target),
        "choices": [label_of(nearest[k]) for k in order],
        "order": [label_of(o) for o in nearest],
        # Where each of `order` meets the target, nearest first.
        "meets": [_group(lineage[d], idx.warmth[lineage[d]["name"]]) for d in reversed(chosen)],
        "tier": tier,
    }


def make_set(ds: Dataset, seed: str) -> list[dict]:
    """The five puzzles a seed names. Raises ValueError for a seed from another
    tree, or a tree with no line-up in it."""
    body = seeds.body_of(seed, game_index(ds).leaves)
    by_label = game_index(ds).by_label
    used: set[str] = set()
    out = []
    for i in range(SET_SIZE):
        p = puzzle(ds, body, i, used)
        used.update(by_label[label]["name"] for label in [p["target"], *p["choices"]])
        out.append(p)
    return out


def pick_seed(ds: Dataset, daily: bool = False, today=None) -> str:
    """A new set's seed: random, or the day's."""
    return seeds.make_seed(game_index(ds).leaves, day=(today or utc_today()) if daily else None)


def score(p: dict, ranking: list[str]) -> int:
    """How many of the four are in their right place, nearest first."""
    return sum(1 for a, b in zip(ranking, p["order"]) if a == b)
