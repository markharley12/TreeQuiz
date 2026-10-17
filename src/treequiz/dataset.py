"""What a dataset is, and where one lives.

A **dataset is a directory** under `datasets/`:

    datasets/<id>/manifest.json   what the tree is about — written by hand
    datasets/<id>/tree.json       the tree to play on — written by a builder
    datasets/<id>/info.json       popup text per node — optional
    datasets/<id>/info-<n>.json   or, for a sized tree, the same in tiers (size.py)

Everything the game needs to know about a *domain* is in the manifest, so the
engine knows nothing about animals, mathematics or languages. That is the whole
point of this repo: TaxoQuiz had "species", "genus" and a Linnaean ladder
written into its code, and every one of those is a manifest field here.

Manifest fields (only `title` is required):

    title         "Fields of mathematics"
    short_title   "Maths" — chips, tabs, the picker
    prompt        one line for the front page
    noun          "field" — what a leaf is called; plural in `noun_plural`
    ladder        {"levels": {"subject": 3, ...}, "top": 4} — rank positions.
                  Optional: with none, every internal node is placed by the
                  tree's shape alone. See ladder.py.
    bulk_unlock   warmth at which bulk guessing opens, 0..1 (default 0.5)
    sources       [{name, url, licence, note}] — attribution, shown in the app
    info_source   what the popup text is, e.g. "Wikipedia" — shown under it
    checks        {"closer": [{"to": name, "order": [name, ...]}]} — orderings
                  of relatedness that must hold; see validate.py
    order         where the tree sits in the app's picker; lower first
    long_labels   true when node names are phrases: the app draws wider boxes
    hide_names    true when node names are opaque keys (Wikidata, Glottolog
                  IDs): the app shows only labels
    chain_order   "root_first" when labels are steps of a path, such as chess
                  moves: a collapsed chain then reads root first, joined by
                  spaces. Default "deepest_first", joined by " › "
    chain_trim    a JavaScript pattern removed from the start of every step
                  but the first in such a chain: chess's "^\\d+…", so that
                  "2.Nf3" then "2…Nc6" read "2.Nf3 Nc6"
    sizes         {"min": 500, "default": 2000, "stops": [500, 1000, 2000]} —
                  the tree can be played cut to its best-known leaves, from
                  `min` to all of them; the daily is always at `default`. Every
                  leaf must then carry `fame`. See size.py

Tree nodes:

    name      unique across the tree; the key for info and for explore
    label     what is displayed, and for a leaf what is guessed; default `name`
    rank      optional; read against the manifest's ladder
    aliases   optional; other things a player might type for this node
    fame      optional, leaves only; a non-negative integer, higher for the
              better known (sitelinks, in a Wikidata tree). What a cut keeps
    children  absent or empty for a leaf

`name` and `label` are separate because the thing that must be unique and
stable is rarely the thing a person wants to read: an MSC code (`05C`) against
"Graph theory", a binomial against "lion".

`$TREEQUIZ_DATASETS` moves the datasets root, which tests use to point at
fixtures. Unset, it is the repo's own `datasets/`, found from this file — fine
for the editable install this project is developed with, and the only install
it has. The frontend reads the same directory at build time.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from .jsonio import read_json
from .size import Sizes, cut

DATASETS_ENV = "TREEQUIZ_DATASETS"
DEFAULT_BULK_UNLOCK = 0.5


def datasets_root() -> Path:
    env = os.environ.get(DATASETS_ENV)
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "datasets"


def available() -> list[str]:
    """Every dataset id with both a manifest and a tree, sorted."""
    root = datasets_root()
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir()
        if (p / "manifest.json").is_file() and (p / "tree.json").is_file()
    )


@dataclass(frozen=True)
class Ladder:
    """Rank name (lower-cased) to a level, with the leaves at `top`.

    Levels need not be integers or contiguous; only their order matters, and
    `top` is what a leaf is worth. The root is pinned at 0 whatever its rank.
    """
    levels: dict[str, float] = field(default_factory=dict)
    top: float = 1.0

    @classmethod
    def from_manifest(cls, spec: dict | None) -> "Ladder":
        if not spec:
            return cls()
        levels = {k.strip().lower(): float(v) for k, v in (spec.get("levels") or {}).items()}
        top = float(spec.get("top", max(levels.values(), default=1.0)))
        if top <= 0:
            raise ValueError(f"ladder top must be positive, got {top}")
        return cls(levels, top)

    def level_of(self, rank: str | None) -> float | None:
        """The ladder level for a rank, or None where the rank is not on it.

        None covers three cases that all want the same treatment: no rank, a
        rank this ladder does not list, and an explicit "clade". All three are
        placed by the tree instead.
        """
        if not rank:
            return None
        return self.levels.get(rank.strip().lower())


@dataclass(frozen=True)
class Dataset:
    id: str
    path: Path
    manifest: dict
    tree: dict

    @cached_property
    def ladder(self) -> Ladder:
        return Ladder.from_manifest(self.manifest.get("ladder"))

    @property
    def title(self) -> str:
        return self.manifest["title"]

    @property
    def noun(self) -> str:
        return self.manifest.get("noun", "leaf")

    @property
    def bulk_unlock(self) -> float:
        return float(self.manifest.get("bulk_unlock", DEFAULT_BULK_UNLOCK))

    @cached_property
    def sizes(self) -> Sizes | None:
        """How the tree may be cut, or None for a tree played whole."""
        return Sizes.from_manifest(self.manifest.get("sizes"))

    @cached_property
    def _cuts(self) -> dict[int, "Dataset"]:
        return {}

    def at_size(self, n: int) -> "Dataset":
        """This dataset cut to its `n` best-known leaves (see size.py), under
        the same id, manifest and info. One object per size, so the engine's
        indexes, which key on the tree, are built once."""
        if n not in self._cuts:
            tree = cut(self.tree, n)
            self._cuts[n] = self if tree is self.tree else Dataset(self.id, self.path, self.manifest, tree)
        return self._cuts[n]

    @cached_property
    def info(self) -> dict:
        """Popup text keyed by node name; empty when the dataset has none.
        A sized tree's tiers are read together: every node's text, whatever
        the size played."""
        p = self.path / "info.json"
        if p.is_file():
            return read_json(p)
        out: dict = {}
        tiers = [q for q in self.path.glob("info-*.json") if q.stem[len("info-"):].isdigit()]
        for tier in sorted(tiers, key=lambda q: int(q.stem[len("info-"):])):
            out.update(read_json(tier))
        return out


# Keyed by resolved path rather than id, so a test pointing $TREEQUIZ_DATASETS
# somewhere else never sees another root's tree under the same id. Nothing
# mutates a loaded tree — every game function builds fresh dicts — so one copy
# is shared by all of them.
_loaded: dict[Path, Dataset] = {}


def load(dataset_id: str, root: Path | None = None) -> Dataset:
    """Load a dataset by id, from the datasets root or from `root` (the tests'
    fixtures). Raises ValueError for one that does not exist, rather than
    falling back to another: playing the wrong tree silently is worse than an
    error."""
    root = root or datasets_root()
    path = (root / dataset_id).resolve()
    if path not in _loaded:
        manifest_path, tree_path = path / "manifest.json", path / "tree.json"
        if not manifest_path.is_file() or not tree_path.is_file():
            raise ValueError(
                f"No dataset {dataset_id!r} under {root} "
                f"(need manifest.json and tree.json). Have: {', '.join(available()) or 'none'}"
            )
        _loaded[path] = Dataset(dataset_id, path, read_json(manifest_path), read_json(tree_path))
    return _loaded[path]


def from_tree(tree: dict, manifest: dict | None = None, dataset_id: str = "inline") -> Dataset:
    """A dataset that lives only in memory — for tests, and for builders that
    validate a tree before writing it."""
    return Dataset(dataset_id, Path("."), manifest or {"title": dataset_id}, tree)


def clear_cache() -> None:
    _loaded.clear()
