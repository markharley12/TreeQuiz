"""Warmth: how specific a node is, 0..1, which is what the tree is coloured by.

A guess is scored by the warmth of its lowest common ancestor with the secret.
This module is TaxoQuiz's `ranks.py` with the Linnaean ladder taken out: the
ladder now comes from the dataset's manifest, and a dataset need not have one.

Three things carry over unchanged, each because it was wrong once there:

* **Rank, not depth.** Depth is not comparable across lineages — a fish at 16
  and a bird at 65 are each a whole species' worth of history — so a scale that
  divides depth by anything paints the same fact different colours in different
  branches. Where a dataset has ranks, a rank means the same everywhere.
* **A rank is a claim and the tree is the evidence.** A level is believed only
  where it is strictly broader than every ranked ancestor and strictly narrower
  than every ranked descendant; both ends of a contradiction are distrusted,
  and ties are rejected. A suborder cannot contain a phylum.
* **Unranked nodes are interpolated**, between the nearest believed ancestor
  and the broadest believed descendant, by steps from each — and placed strictly
  warmer than their parent, so going deeper never gets colder or stays level.

What is new, and why:

* **The root and the leaves are anchors**, at 0 and at the ladder's `top`,
  whatever their rank labels say. Everything shares the root, so sharing it is
  the coldest thing that can be said; and a leaf is the thing guessed, so
  finding it must reach the top of the scale. In TaxoQuiz both were true by
  construction (a kingdom root, species leaves, and the validator failing a
  leaf that was not one); here they are rules, because a tree of languages or
  countries has no kingdom and no species.
* **A ladder is optional.** With none, only the anchors are ranked and every
  internal node is interpolated, which makes its warmth the fraction of the way
  down the longest path beneath it. That is a depth measure, and the warning
  above applies — but it is normalised per lineage, by the length of that
  lineage, which is the most a shape alone can say.
* **Ties below go to the longer path.** When several descendants share the
  broadest believed level (always, with no ladder: every leaf is at the top),
  a node is placed against the one furthest away. TaxoQuiz took whichever came
  first in child order, which made a family's warmth depend on how its genera
  happened to be sorted. Longest is the conservative choice: a group is never
  painted warmer than its deepest member's ancestry warrants.

Not normalised against the secret's own depth or rank, however tidy that would
look: it would leak where the secret sits, which the `???` node exists to hide.
"""
from __future__ import annotations

from .dataset import Ladder
from .tree import children_of


def _warmth(level: float, ladder: Ladder) -> float:
    return min(max(level / ladder.top, 0.0), 1.0)


def believed_levels(tree: dict, ladder: Ladder) -> dict[int, float | None]:
    """Each node's ladder level keyed by `id(node)`, or None where its rank is
    not believed (or it has none). The root is 0 and every leaf is `top`."""
    raw: dict[int, float | None] = {}
    par_max: dict[int, float | None] = {}
    min_desc: dict[int, float | None] = {}

    def down(node: dict, best: float | None, is_root: bool) -> None:
        if not children_of(node):
            own: float | None = ladder.top
        elif is_root:
            own = 0.0
        else:
            own = ladder.level_of(node.get("rank"))
        raw[id(node)] = own
        par_max[id(node)] = best
        deeper = best if own is None else (own if best is None else max(best, own))
        for child in children_of(node):
            down(child, deeper, False)

    down(tree, None, True)

    def up(node: dict) -> float | None:
        best: float | None = None
        for child in children_of(node):
            for cand in (up(child), raw[id(child)]):
                if cand is not None and (best is None or cand < best):
                    best = cand
        min_desc[id(node)] = best
        return best

    up(tree)

    believed: dict[int, float | None] = {}

    def judge(node: dict, is_root: bool) -> None:
        own = raw[id(node)]
        keep = own
        # Anchors are never judged: the root and the leaves are what every
        # other claim is judged against.
        if own is not None and not is_root and children_of(node):
            above, below = par_max[id(node)], min_desc[id(node)]
            if (above is not None and own <= above) or (below is not None and own >= below):
                keep = None
        believed[id(node)] = keep
        for child in children_of(node):
            judge(child, False)

    judge(tree, True)
    return believed


def warmth_by_name(tree: dict, ladder: Ladder) -> dict[str, float]:
    """Every node name mapped to its warmth, 0..1."""
    believed = believed_levels(tree, ladder)
    out: dict[str, float] = {}

    # Pass 1, bottom-up: the broadest believed level below each node, and how
    # many steps down it is — the furthest such node on a tie.
    below: dict[int, tuple[float, int] | None] = {}

    def broadest_below(node: dict) -> tuple[float, int] | None:
        best: tuple[float, int] | None = None
        for child in children_of(node):
            # Recurse unconditionally: every node needs its own entry, the
            # believed ones included.
            deeper = broadest_below(child)
            own = believed[id(child)]
            if own is not None:
                cand: tuple[float, int] | None = (own, 1)
            else:
                cand = None if deeper is None else (deeper[0], deeper[1] + 1)
            if cand is not None and (
                best is None or cand[0] < best[0] or (cand[0] == best[0] and cand[1] > best[1])
            ):
                best = cand
        below[id(node)] = best
        return best

    broadest_below(tree)

    # Pass 2, top-down: the nearest believed ancestor's level and distance.
    def walk_down(node: dict, anc: float, steps: int, floor: float) -> None:
        own = believed[id(node)]
        if own is not None:
            value = _warmth(own, ladder)
            anc, steps = own, 0
        else:
            steps += 1
            found = below[id(node)]
            if found is None:
                value = _warmth(anc, ladder)
            else:
                desc, down = found
                value = _warmth(anc + (desc - anc) * (steps / (steps + down)), ladder)
                # Strictly warmer than the parent. A node placed against the
                # broadest rank below *it* can land at or under its parent, which
                # was placed against a different one; it then goes a share of the
                # way from the parent to that rank instead, which keeps it below
                # every believed descendant.
                if value <= floor:
                    value = floor + (_warmth(desc, ladder) - floor) / (down + 1)
            value = max(value, floor)
        out[node["name"]] = value
        for child in children_of(node):
            walk_down(child, anc, steps, value)

    walk_down(tree, 0.0, 0, 0.0)
    return out


def rejected_share(tree: dict, ladder: Ladder) -> tuple[int, int]:
    """(rejected, ranked) over internal non-root nodes whose rank is on the
    ladder. The early-warning number: a healthy dataset rejects almost none."""
    believed = believed_levels(tree, ladder)
    rejected = ranked = 0

    def walk(node: dict, is_root: bool) -> None:
        nonlocal rejected, ranked
        if not is_root and children_of(node) and ladder.level_of(node.get("rank")) is not None:
            ranked += 1
            if believed[id(node)] is None:
                rejected += 1
        for c in children_of(node):
            walk(c, False)

    walk(tree, True)
    return rejected, ranked
