"""What these scripts took from TaxoQuiz's `taxoquiz` package, re-homed.

The scripts in this directory are TaxoQuiz's datagen, ported (Oct 2026). There
they imported paths, tree helpers and ranks from the game itself; TreeQuiz's
engine knows nothing about species, so the handful they used live here instead,
and the rest of each script is as TaxoQuiz left it.

**Where things are.** Everything is under one work directory, gitignored:

    datagen/_cache/animals-full/_raw/      the scrape: Wikidata species and
                                           ancestors, the raw tree, the Catalogue
                                           of Life's answers (TaxoQuiz's data/_cache)
    datagen/_cache/animals-full/<name>/    a *staging* tree in TaxoQuiz's shape,
                                           tree.json + taxon_info.json — what
                                           extract_game_tree.py and
                                           scrape_taxon_info.py write; `game` by
                                           default (TaxoQuiz's data/<name>/)

`build_animals_full.py` converts a staging tree into `datasets/animals-full/`.
A staging tree stays in TaxoQuiz's shape (binomial in `name`, English in
`common_name`, a `qid` on every node) because every script here reads that
shape, and the conversion is one function rather than eight ports.

`$ANIMALS_FULL_DIR` moves the work directory, which the tests use, and
`$ANIMALS_FULL_DATASET` picks the staging tree, as `$TAXOQUIZ_DATASET` did.

**Ranks** are TreeQuiz's ladder (`treequiz.ladder`) read with the animals-full
manifest's levels, which are TaxoQuiz's `LEVELS`. Two differences from
TaxoQuiz's `ranks.py`, both documented in `ladder.py`: the root is pinned at 0
and leaves at the top whatever their ranks, and ties below go to the longer
path. On the animals tree the second moved 2 of 1,615 nodes.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from treequiz import ladder as _ladder  # noqa: E402
from treequiz.dataset import Ladder  # noqa: E402
from treequiz.jsonio import read_json, write_json_atomic  # noqa: E402,F401  (re-exported)

DATASET_ID = "animals-full"
MANIFEST = REPO / "datasets" / DATASET_ID / "manifest.json"

WORK_ENV = "ANIMALS_FULL_DIR"
DATASET_ENV = "ANIMALS_FULL_DATASET"
DEFAULT_DATASET = "game"

# Files in cache_dir(). `-raw` on the tree is load-bearing: it is not a tree
# anything plays. It is rooted at Life, names nodes in English, and its names
# are not unique; extract_game_tree.py converts it.
CACHE_SPECIES = "wikidata-species.json"
CACHE_ANCESTORS = "wikidata-ancestors.json"
CACHE_RAW_TREE = "wikidata-tree-raw.json"


def data_dir() -> Path:
    """The work directory. Override with $ANIMALS_FULL_DIR."""
    env = os.environ.get(WORK_ENV)
    return Path(env) if env else REPO / "datagen" / "_cache" / DATASET_ID


def cache_dir() -> Path:
    """The scrape's caches. Rebuildable, never read by the app, safe to delete
    at the cost of scraping again. Underscored so no staging tree can share
    its name."""
    return data_dir() / "_raw"


def current_dataset() -> str:
    return os.environ.get(DATASET_ENV) or DEFAULT_DATASET


def dataset_dir(name: str | None = None) -> Path:
    return data_dir() / (name or current_dataset())


def available_datasets() -> list[str]:
    """Staging trees with a tree.json, sorted."""
    root = data_dir()
    if not root.is_dir():
        return []
    return sorted(p.name for p in root.iterdir()
                  if p.is_dir() and not p.name.startswith(("_", ".")) and (p / "tree.json").is_file())


def tree_path(name: str | None = None) -> Path:
    """A staging tree. Missing raises, rather than falling back to another:
    being dropped quietly onto the wrong tree is what this layout prevents."""
    path = dataset_dir(name) / "tree.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No staging tree at {path}. Have: {', '.join(available_datasets()) or 'none'}. "
            f"build_animals_full.py seeds one from TaxoQuiz; extract_game_tree.py makes one."
        )
    return path


def taxon_info_path(name: str | None = None) -> Path:
    """Where a staging tree's popup text is written."""
    return dataset_dir(name) / "taxon_info.json"


def taxon_info_read_path(name: str | None = None) -> Path | None:
    """Where to read it, or None. No fallback: one tree's text against
    another's nodes is the mismatch that keeps them in one directory."""
    own = taxon_info_path(name)
    return own if own.is_file() else None


# --------------------------------------------------------------------------
# Tree helpers, from taxoquiz.game.tree
# --------------------------------------------------------------------------

_trees: dict[str, dict] = {}


def load_tree(path: Path | None = None) -> dict:
    """A staging tree, parsed once per path. Nothing mutates it."""
    key = str(Path(path) if path is not None else tree_path())
    if key not in _trees:
        _trees[key] = read_json(key)
    return _trees[key]


def clear_cache() -> None:
    _trees.clear()
    _ladder_spec.cache_clear()


def get_species(node: dict) -> list[dict]:
    """Every leaf, in tree order."""
    if not node.get("children"):
        return [node]
    out: list[dict] = []
    for child in node["children"]:
        out.extend(get_species(child))
    return out


def get_ancestors(node: dict) -> list[dict]:
    """Every internal node, parents before children: what the popup can be
    opened on besides the species, derived from the tree rather than listed."""
    if not node.get("children"):
        return []
    out = [node]
    for child in node["children"]:
        out.extend(get_ancestors(child))
    return out


def _collect(tree: dict, key: str, leaves_only: bool = False) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node: dict) -> None:
        if node.get(key) and not (leaves_only and node.get("children")):
            out[node["name"]] = node[key]
        for child in node.get("children") or []:
            walk(child)

    walk(tree)
    return out


def qid_of(tree: dict) -> dict[str, str]:
    """Node name to Wikidata Q-ID, for nodes that carry one."""
    return _collect(tree, "qid")


def common_name_of(tree: dict) -> dict[str, str]:
    """Node name to English name, for the species that have one."""
    return _collect(tree, "common_name", leaves_only=True)


# --------------------------------------------------------------------------
# Ranks, from taxoquiz.ranks, on TreeQuiz's ladder
# --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _ladder_spec() -> Ladder:
    return Ladder.from_manifest(read_json(MANIFEST).get("ladder"))


def level_of(rank: str | None) -> float | None:
    """The ladder level of a rank, or None where it is not on the ladder."""
    return _ladder_spec().level_of(rank)


def believed_levels(tree: dict) -> dict[int, float | None]:
    """Each node's level by `id(node)`, or None where its rank is not believed."""
    return _ladder.believed_levels(tree, _ladder_spec())


def rank_levels(tree: dict) -> dict[str, float]:
    """Every node name to its warmth, 0..1."""
    return _ladder.warmth_by_name(tree, _ladder_spec())
