"""Walks over a tree that every other module shares.

Nothing here mutates a node. Callers that need a changed tree build fresh dicts,
which is what lets one parsed copy serve every module.
"""
from __future__ import annotations


def children_of(node: dict) -> list[dict]:
    """`node.get("children") or []` — a missing list and an empty one both
    mean a leaf."""
    return node.get("children") or []


def is_leaf(node: dict) -> bool:
    return not children_of(node)


def label_of(node: dict) -> str:
    """What a node is displayed as, and for a leaf what is guessed."""
    return node.get("label") or node["name"]


def leaves(node: dict) -> list[dict]:
    """Every leaf, in tree order. The order is load-bearing: seeds index into it."""
    out: list[dict] = []

    def walk(n: dict) -> None:
        kids = children_of(n)
        if not kids:
            out.append(n)
        for c in kids:
            walk(c)

    walk(node)
    return out


def internal_nodes(node: dict) -> list[dict]:
    """Every node with children, parents before their children."""
    out: list[dict] = []

    def walk(n: dict) -> None:
        kids = children_of(n)
        if kids:
            out.append(n)
        for c in kids:
            walk(c)

    walk(node)
    return out


def all_nodes(node: dict) -> list[dict]:
    out: list[dict] = []

    def walk(n: dict) -> None:
        out.append(n)
        for c in children_of(n):
            walk(c)

    walk(node)
    return out


def by_name(tree: dict) -> dict[str, dict]:
    return {n["name"]: n for n in all_nodes(tree)}
