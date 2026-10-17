"""One tree at many sizes: the best-known `n` leaves, and nothing else.

TaxoQuiz sized its datasets by a sitelink threshold — a species was in when at
least that many Wikipedias covered it — and since a species' count does not
depend on the query, every smaller dataset was exactly a subset of every
bigger one. So one tree is enough for every size: the builder writes a `fame`
on each leaf (its sitelinks, for a Wikidata tree), the tree ships whole, and
the engine cuts it. A cut to `n` is the threshold rule restated as a count.

**The cut** keeps the `n` leaves of highest fame, ties broken by `name`
ascending (by code point, which the port has to take care to match), and
drops every internal node left with no leaf. Nothing else changes: a node left
with one child stays, as a pass-through, because TaxoQuiz's threshold builds
left them too (`extract_game_tree.py` drops childless taxa and merges a child
named as its parent, and nothing more). Splicing them out would also make a
node's entry size depend on its siblings, and the info tiers below rely on
every node, once in, staying in at every larger size.

Everything else — warmth, seeds, hints, odd one out, line-up, explore — runs
on the cut tree as on any other, so a node's warmth is the cut tree's: without
a ladder it is placed by the paths left below it.

A leaf with no `fame` counts as 0. The validator requires one on every leaf of
a tree whose manifest has `sizes`, so that only matters for a tree that has
not opted in.

**Sizes** in a manifest opt a tree into the slider:

    "sizes": {"min": 500, "default": 2000, "stops": [500, 1000, 2000, 5000]}

The slider snaps to the stops and to the whole tree beyond the last one;
`default` is the size the daily is always played at, so everyone gets the
same one. `stops` may be left out, for `[min, default]`.

**Info tiers.** A sized tree's popup text may be split by when a node enters:
`info-<n>.json` holds the nodes that first appear when the tree is cut to `n`
and were not there at the previous stop, and the last tier is named for the
tree's leaf count. Playing at a size then needs only the tiers up to it.
`tiers` says which tier each node belongs to, for the builder that writes them.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tree import children_of, leaves


def fame_of(leaf: dict) -> int:
    return leaf.get("fame") or 0


def ranked(tree: dict) -> list[dict]:
    """Every leaf, best known first: fame descending, then name ascending.
    The first `n` are what a cut to `n` keeps."""
    return sorted(leaves(tree), key=lambda x: (-fame_of(x), x["name"]))


def _keep(node: dict, kept: set[str]) -> dict | None:
    kids = children_of(node)
    if not kids:
        return node if node["name"] in kept else None
    out = [k for k in (_keep(c, kept) for c in kids) if k is not None]
    if not out:
        return None
    # An untouched subtree is the same object, so a cut shares what it keeps.
    if len(out) == len(kids) and all(a is b for a, b in zip(out, kids)):
        return node
    return {**node, "children": out}


def cut(tree: dict, n: int) -> dict:
    """The tree with only its `n` best-known leaves, and the nodes above them.
    `n` at or past the leaf count is the whole tree, the same object."""
    if n < 1:
        raise ValueError(f"A tree cut to {n} leaves has none; the smallest cut is 1.")
    order = ranked(tree)
    if n >= len(order):
        return tree
    kept = _keep(tree, {x["name"] for x in order[:n]})
    assert kept is not None  # n >= 1, so at least one leaf and the root survive
    return kept


def entry_ranks(tree: dict) -> dict[str, int]:
    """For every node, the smallest cut that holds it: one more than the
    position, in `ranked` order, of its best-known leaf."""
    rank = {x["name"]: i + 1 for i, x in enumerate(ranked(tree))}
    out: dict[str, int] = {}

    def walk(node: dict) -> int:
        kids = children_of(node)
        best = rank[node["name"]] if not kids else min(walk(c) for c in kids)
        out[node["name"]] = best
        return best

    walk(tree)
    return out


@dataclass(frozen=True)
class Sizes:
    min: int
    default: int
    stops: tuple[int, ...]

    @classmethod
    def from_manifest(cls, spec: dict | None) -> "Sizes | None":
        """None for a tree with no `sizes`. Raises ValueError for one that
        does not make sense, whatever the tree."""
        if not spec:
            return None
        lo, default = spec.get("min"), spec.get("default")
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (lo, default)):
            raise ValueError(f"sizes needs integer min and default, got {spec!r}")
        stops = spec.get("stops") or sorted({lo, default})
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in stops):
            raise ValueError(f"sizes.stops must be integers, got {stops!r}")
        if any(a >= b for a, b in zip(stops, stops[1:])):
            raise ValueError(f"sizes.stops must rise strictly, got {stops!r}")
        if stops[0] != lo or lo < 2:
            raise ValueError(f"sizes.min must be the first stop and at least 2, got {lo} and {stops!r}")
        if default not in stops:
            raise ValueError(f"sizes.default {default} is not one of the stops {stops!r}")
        return cls(lo, default, tuple(stops))


def tiers(tree: dict, stops: tuple[int, ...] | list[int]) -> dict[str, int]:
    """Which info tier each node belongs to: the first stop whose cut holds
    it, or the leaf count for a node only the whole tree has."""
    whole = len(leaves(tree))
    bounds = [s for s in stops if s < whole] + [whole]
    out = {}
    for name, r in entry_ranks(tree).items():
        out[name] = next(b for b in bounds if r <= b)
    return out
