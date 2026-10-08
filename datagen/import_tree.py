#!/usr/bin/env python3
"""Make a dataset from a tree you wrote yourself — the quickest way to a new one.

Two input formats, chosen by extension:

**An outline (`.txt`)**, one node per line, indented by its depth:

    # comments and blank lines are ignored
    Mathematics
      Algebra | Branch
        Group theory | Subject | groups
        Ring theory | Subject
      Analysis | Branch
        Real analysis | Subject | calculus, epsilon-delta

Each line is `label | rank | alias, alias`, the rank and aliases optional.
Indent with spaces or tabs, consistently; a line deeper than the one before it
is its child. A node's `name` is its label, so labels must be unique; give one
an explicit name with `label <name>` where two would collide.

**A table (`.csv`)** with a header row: `name,parent` required, `label`,
`rank` and `aliases` (semicolon-separated) optional. Exactly one row has an
empty parent — the root. Rows may come in any order; children keep the order
they appear in.

The dataset directory needs a manifest before a tree is written into it (the
words are yours to choose); `--init` writes a starter one to edit. The tree is
validated like every other dataset's, and refused if it fails.

Usage:
    python3 datagen/import_tree.py my-tree.txt --id mytree --init
    python3 datagen/import_tree.py edges.csv --id mytree
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from common import REPO, node, write_dataset, write_json_atomic

_EXPLICIT_NAME = re.compile(r"^(.*?)\s*<([^<>]+)>\s*$")


def parse_outline(text: str) -> dict:
    """An indented outline to a tree. Raises ValueError, naming the line, for
    anything ambiguous: two roots, a jump of more than one level, a name used
    twice."""
    stack: list[tuple[int, dict]] = []   # (indent, node) from the root down
    root: dict | None = None
    unit: str | None = None
    names: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent_text = raw[: len(raw) - len(raw.lstrip())]
        if indent_text and unit is None:
            unit = indent_text
        if unit and indent_text.replace(unit, ""):
            raise ValueError(f"line {lineno}: mixed or uneven indentation")
        depth = len(indent_text) // len(unit) if unit else 0
        fields = [f.strip() for f in raw.strip().split("|")]
        label, name = fields[0], fields[0]
        m = _EXPLICIT_NAME.match(label)
        if m:
            label, name = m.group(1), m.group(2).strip()
        if not label:
            raise ValueError(f"line {lineno}: no label")
        if name in names:
            raise ValueError(f"line {lineno}: {name!r} is used twice; give one a <name>")
        names.add(name)
        rank = fields[1] if len(fields) > 1 and fields[1] else None
        aliases = [a.strip() for a in fields[2].split(",") if a.strip()] if len(fields) > 2 else None
        n = node(name, rank, label=label, aliases=aliases)

        if depth == 0:
            if root is not None:
                raise ValueError(f"line {lineno}: a second root, {label!r}; a tree has one")
            root = n
            stack = [(0, n)]
            continue
        if root is None:
            raise ValueError(f"line {lineno}: indented before any root")
        if depth > stack[-1][0] + 1:
            raise ValueError(f"line {lineno}: {label!r} is indented more than one level past its parent")
        while stack[-1][0] >= depth:
            stack.pop()
        stack[-1][1].setdefault("children", []).append(n)
        stack.append((depth, n))
    if root is None:
        raise ValueError("the outline is empty")
    return root


def parse_csv(text: str) -> dict:
    rows = list(csv.DictReader(text.splitlines()))
    if not rows or not {"name", "parent"} <= set(rows[0]):
        raise ValueError("the CSV needs a header with at least name and parent")
    nodes: dict[str, dict] = {}
    kids: dict[str, list[str]] = {}
    roots = []
    for i, r in enumerate(rows, 2):
        name = (r.get("name") or "").strip()
        if not name:
            raise ValueError(f"row {i}: no name")
        if name in nodes:
            raise ValueError(f"row {i}: {name!r} appears twice")
        aliases = [a.strip() for a in (r.get("aliases") or "").split(";") if a.strip()] or None
        nodes[name] = node(name, (r.get("rank") or "").strip() or None,
                           label=(r.get("label") or "").strip() or None, aliases=aliases)
        parent = (r.get("parent") or "").strip()
        if parent:
            kids.setdefault(parent, []).append(name)
        else:
            roots.append(name)
    if len(roots) != 1:
        raise ValueError(f"exactly one row must have no parent; found {len(roots)}: {roots[:5]}")
    missing = sorted(set(kids) - set(nodes))
    if missing:
        raise ValueError(f"parents with no row of their own: {missing[:5]}")

    seen: set[str] = set()

    def build(name: str) -> dict:
        if name in seen:
            raise ValueError(f"{name!r} is its own ancestor")
        seen.add(name)
        out = dict(nodes[name])
        if name in kids:
            out["children"] = [build(c) for c in kids[name]]
        return out

    tree = build(roots[0])
    unreached = sorted(set(nodes) - seen)
    if unreached:
        raise ValueError(f"rows not under the root (a cycle?): {unreached[:5]}")
    return tree


STARTER_MANIFEST = {
    "title": "",
    "short_title": "",
    "prompt": "Guess the secret … by where it sits in the tree.",
    "blurb": "One line for the front page: how many, of what, from where.",
    "noun": "leaf",
    "noun_plural": "leaves",
    "bulk_unlock": 0.5,
    "sources": [{"name": "", "url": "", "licence": "", "note": ""}],
    "checks": {"closer": []},
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=Path)
    ap.add_argument("--id", required=True, help="the dataset's directory name under datasets/")
    ap.add_argument("--init", action="store_true", help="write a starter manifest if there is none")
    args = ap.parse_args()

    text = args.source.read_text(encoding="utf-8")
    tree = parse_csv(text) if args.source.suffix.lower() == ".csv" else parse_outline(text)
    manifest = REPO / "datasets" / args.id / "manifest.json"
    if args.init and not manifest.exists():
        write_json_atomic(manifest, {**STARTER_MANIFEST, "title": tree.get("label") or tree["name"],
                                     "short_title": tree.get("label") or tree["name"]})
        print(f"wrote a starter {manifest} — edit its words, sources and checks")
    write_dataset(args.id, tree)


if __name__ == "__main__":
    main()
