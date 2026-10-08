"""Free browsing of a tree, with no game attached. TaxoQuiz's `explore.py`.

The tree is served in **slices**: a request names a root and a node budget,
and nodes with children beyond it come back `truncated`, for the client to
fetch when they are opened. A budget spent breadth-first, not a depth: a real
tree opens with single-child chains, where three levels is three nodes, and has
bushes where three levels is hundreds.

Every node carries `leaf_count`. Browsing without it is guesswork: two labels
look alike, and one holds a thousand leaves while the other holds three.
"""
from __future__ import annotations

from collections import namedtuple

from .dataset import Dataset
from .ladder import warmth_by_name
from .tree import children_of, label_of

_Index = namedtuple("_Index", "tree by_name parent depth leaf_count node_count warmth")
_indexes: dict[int, tuple[dict, _Index]] = {}

LINEAGE_TARGET_BUDGET = 60


def index(ds: Dataset) -> _Index:
    cached = _indexes.get(id(ds.tree))
    if cached is not None and cached[0] is ds.tree:
        return cached[1]
    by_name: dict[str, dict] = {}
    parent: dict[str, str] = {}
    depth: dict[str, int] = {}
    leaf_count: dict[str, int] = {}
    node_count: dict[str, int] = {}

    def walk(node: dict, parent_name: str | None, d: int) -> tuple[int, int]:
        name = node["name"]
        by_name[name] = node
        depth[name] = d
        if parent_name is not None:
            parent[name] = parent_name
        kids = children_of(node)
        if not kids:
            leaf_count[name] = node_count[name] = 1
            return 1, 1
        lv = nodes = 0
        for child in kids:
            a, b = walk(child, name, d + 1)
            lv += a
            nodes += b
        leaf_count[name] = lv
        node_count[name] = nodes + 1
        return lv, nodes + 1

    walk(ds.tree, None, 0)
    idx = _Index(ds.tree, by_name, parent, depth, leaf_count, node_count, warmth_by_name(ds.tree, ds.ladder))
    _indexes[id(ds.tree)] = (ds.tree, idx)
    return idx


def clear_cache() -> None:
    _indexes.clear()


def _select(node: dict, depth: int | None, budget: int | None) -> set[str]:
    """Names to include, grown a whole level at a time until a limit bites."""
    included = {node["name"]}
    frontier = [node]
    level = 0
    while frontier and (depth is None or level < depth):
        nxt = [c for n in frontier for c in children_of(n)]
        if not nxt:
            break
        if budget is not None and len(included) + len(nxt) > budget:
            break
        included.update(n["name"] for n in nxt)
        frontier = nxt
        level += 1
    return included


def _node_dict(node: dict, included: set[str] | None, idx: _Index) -> dict:
    """`included is None` serialises the node alone, as a stub."""
    name = node["name"]
    kids = children_of(node)
    kept = [c for c in kids if included is not None and c["name"] in included]
    return {
        "name": name,
        "label": label_of(node),
        "rank": node.get("rank", ""),
        "depth": idx.depth[name],
        # Not derivable on the client: an unranked node is placed from ranked
        # nodes around it in the whole tree, most of which a slice lacks.
        "warmth": idx.warmth[name],
        "child_count": len(kids),
        "leaf_count": idx.leaf_count[name],
        # What a full expand would render, so the UI can warn before it does.
        "node_count": idx.node_count[name],
        "truncated": len(kept) < len(kids),
        "children": [_node_dict(c, included, idx) for c in kept],
    }


def _unknown(name: str) -> ValueError:
    return ValueError(f"Not in this dataset: {name!r}")


def subtree(ds: Dataset, root: str | None = None, depth: int | None = None, budget: int | None = 200) -> dict:
    """The subtree at `root`. An unknown root raises rather than falling back to
    the whole tree, which would look like it had worked."""
    idx = index(ds)
    node = idx.tree if root is None else idx.by_name.get(root)
    if node is None:
        raise _unknown(root)
    return _node_dict(node, _select(node, depth, budget), idx)


def path_to(ds: Dataset, name: str) -> list[str]:
    idx = index(ds)
    if name not in idx.by_name:
        raise _unknown(name)
    chain = [name]
    while chain[-1] in idx.parent:
        chain.append(idx.parent[chain[-1]])
    return list(reversed(chain))


def lineage(ds: Dataset, name: str) -> dict:
    """The tree from the root to `name` with siblings at every level, in one
    piece, and a normal slice at the target so you land on something to read."""
    idx = index(ds)
    chain = path_to(ds, name)

    def build(node: dict, i: int) -> dict:
        if i + 1 >= len(chain):
            return _node_dict(node, _select(node, None, LINEAGE_TARGET_BUDGET), idx)
        nxt = chain[i + 1]
        out = _node_dict(node, None, idx)
        out["children"] = [
            build(c, i + 1) if c["name"] == nxt else _node_dict(c, None, idx)
            for c in children_of(node)
        ]
        out["truncated"] = False
        return out

    return {"path": chain, "tree": build(idx.tree, 0)}


def search(ds: Dataset, query: str, limit: int = 25) -> list[dict]:
    """Nodes whose name, label or an alias contains `query`: prefix matches
    first, then bigger groups, then by name."""
    idx = index(ds)
    needle = query.strip().lower()
    if not needle:
        return []
    hits = []
    for name, node in idx.by_name.items():
        hays = [label_of(node).lower(), name.lower(), *(a.lower() for a in node.get("aliases") or [])]
        matched = [h for h in hays if needle in h]
        if not matched:
            continue
        prefix = 0 if any(h.startswith(needle) for h in matched) else 1
        hits.append((prefix, -idx.leaf_count[name], name, node))
    hits.sort(key=lambda h: (h[0], h[1], h[2]))
    return [
        {
            "name": name,
            "label": label_of(node),
            "rank": node.get("rank", ""),
            "depth": idx.depth[name],
            "leaf_count": idx.leaf_count[name],
            "is_leaf": not children_of(node),
        }
        for _, _, name, node in hits[:limit]
    ]


def stats(ds: Dataset) -> dict:
    idx = index(ds)
    root = idx.tree["name"]
    return {
        "root": root,
        "nodes": idx.node_count[root],
        "leaves": idx.leaf_count[root],
        "max_depth": max(idx.depth.values()),
    }
