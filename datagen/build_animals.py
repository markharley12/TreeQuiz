#!/usr/bin/env python3
"""datasets/animals — TaxoQuiz's 530-species example, in the generic shape.

This dataset is the abstraction's proof: TaxoQuiz's whole game, rebuilt from a
manifest and a tree with nothing about biology left in the engine. The Linnaean
ladder that was `taxoquiz/ranks.py`'s `LEVELS` is the manifest's `ladder`, and
TaxoQuiz's validator's ground-truth table is the manifest's `checks`.

The conversion:

- a species keeps its binomial as `name` (unique, and what the popup text is
  keyed by) and takes its common name as `label`, which is what is guessed;
  the binomial goes in `aliases` too, so typing "panthera" suggests the lion;
- the popup text keeps every field but the Q-ID, renamed to the generic ones.

Usage:
    python3 datagen/build_animals.py [--taxoquiz ../TaxoQuiz]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import REPO, node, read_json, write_dataset


def convert(n: dict) -> dict:
    kids = n.get("children") or []
    if not kids:
        sci = n["name"]
        return node(sci, n.get("rank"), label=n["common_name"], aliases=[sci])
    return node(n["name"], n.get("rank"), children=[convert(c) for c in kids])


def convert_info(info: dict) -> dict:
    out = {}
    for name, e in info.items():
        entry = {"description": e.get("description", "")}
        if e.get("image_url"):
            entry["image_url"] = e["image_url"]
        if e.get("wikipedia_url"):
            entry["url"] = e["wikipedia_url"]
            entry["url_title"] = e.get("wikipedia_title") or name
        out[name] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--taxoquiz", type=Path, default=REPO.parent / "TaxoQuiz")
    args = ap.parse_args()
    data = args.taxoquiz / "src" / "taxoquiz" / "data"
    tree = convert(read_json(data / "example_tree.json"))
    info = convert_info(read_json(data / "example_taxon_info.json"))
    write_dataset("animals", tree, info)


if __name__ == "__main__":
    main()
