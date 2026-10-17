#!/usr/bin/env python3
"""datasets/animals-full — TaxoQuiz Full's 41,000 animals, with a fame on each.

`build_animals.py` converts TaxoQuiz's hand-curated 530; this converts the tree
its Wikidata pipeline builds, which is now `datagen/animals_full/` (see its
README). The pipeline writes a *staging tree* in TaxoQuiz's shape under
`datagen/_cache/animals-full/`; this turns it into TreeQuiz's, the same way
`build_animals.py` does:

- a species keeps its binomial as `name`, takes its English name as `label`,
  and lists the binomial in `aliases`, so typing "panthera" suggests the lion;
- a taxon with an English label (Q7377 is "mammal") lists it in `aliases`, so
  explore's search finds Mammalia by "mammal";
- **every leaf gets `fame`, its Wikidata sitelinks**, from the species cache —
  how many Wikipedias have an article on it. That is the number TaxoQuiz sized
  its scrapes by, and since a species' count does not depend on the query,
  keeping the N most famous leaves of this one tree is exactly the scrape at
  that threshold (`docs/scaling.md`). The size slider cuts by it;
- the Q-IDs and the staging tree's second copy of each binomial are dropped:
  the app reads neither, and the staging tree keeps both.

**Popup text is split into tiers** by when a node enters the tree. A node
enters when its most famous leaf does: cut to `n` (fame descending, then name),
the node is in once that leaf's place is under `n`. `info-<n>.json` holds the
nodes that enter at stop `n` and not at the stop before, for each of the
manifest's `sizes.stops` and then the leaf count. Playing at 2,000 then fetches
the first three tiers rather than all 57,000 entries.

**What is committed.** Only `datasets/animals-full/manifest.json`, by hand. The
tree and the tiers are built here, gitignored, and published as a GitHub
Release named by the manifest's `release` (`publish_release.py`, which asks
first). Whatever has `release` in its manifest is a remote tree: the
conformance file leaves it out, because a clean clone does not have it.

**No scrape by default.** A fresh work directory is seeded from TaxoQuiz's
checkout: its caches (`data/_cache/`, for the sitelinks and the pipeline) and
its last extracted tree and text (`data/wikidata-parents-fixed/`). Copied, not
linked, so a later scrape here never writes into TaxoQuiz. Seeding never
overwrites; to refresh the data, run the pipeline (`datagen/animals_full/`'s
README has the order) and then this.

Usage:
    python3 datagen/build_animals_full.py [--taxoquiz ../TaxoQuiz] [--dataset game]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from build_animals import convert_info
from common import REPO, node, read_json, write_dataset, write_json_atomic

sys.path.insert(0, str(Path(__file__).resolve().parent / "animals_full"))
import taxo  # noqa: E402
from seed_taxon_info import seeded  # noqa: E402

DATASET = taxo.DATASET_ID
OUT = REPO / "datasets" / DATASET

# What a fresh work directory is seeded with, from a TaxoQuiz checkout.
CACHES = (taxo.CACHE_SPECIES, taxo.CACHE_ANCESTORS, taxo.CACHE_RAW_TREE,
          "col-names.json", "synonym-report.json")
TAXOQUIZ_TREE = Path("data") / "wikidata-parents-fixed"

# Wikipedia's page images come back tagged for its analytics; the picture is
# the same without, and 57,000 copies of the tag are about 4MB.
UTM = "?utm_source=en.wikipedia.org&utm_campaign=api&utm_content=thumbnail"


def seed(taxoquiz: Path, name: str) -> None:
    """Fill what the work directory lacks from TaxoQuiz's checkout."""
    if not (taxoquiz / "data").is_dir():
        print(f"note: no TaxoQuiz data at {taxoquiz / 'data'} to seed from (pass --taxoquiz)")
        return
    caches = taxo.cache_dir()
    for f in CACHES:
        src, dst = taxoquiz / "data" / "_cache" / f, caches / f
        if not dst.exists() and src.is_file():
            caches.mkdir(parents=True, exist_ok=True)
            print(f"seeding {dst} from {src}")
            shutil.copyfile(src, dst)
    staged = taxo.dataset_dir(name)
    src_tree = taxoquiz / TAXOQUIZ_TREE / "tree.json"
    if not (staged / "tree.json").exists() and src_tree.is_file():
        staged.mkdir(parents=True, exist_ok=True)
        print(f"seeding {staged / 'tree.json'} from {src_tree}")
        shutil.copyfile(src_tree, staged / "tree.json")
    src_info = taxoquiz / TAXOQUIZ_TREE / "taxon_info.json"
    dst_info = taxo.taxon_info_path(name)
    if not dst_info.exists() and src_info.is_file() and (staged / "tree.json").exists():
        kept, absent, mismatched = seeded(read_json(src_info), taxo.qid_of(read_json(staged / "tree.json")))
        print(f"seeding {dst_info} from {src_info}: {len(kept):,} kept, "
              f"{absent:,} not in the tree, {mismatched:,} Q-ID mismatches")
        write_json_atomic(dst_info, kept, indent=None)


def fame_of(staging: dict, species: dict[str, dict]) -> dict[str, int]:
    """Leaf name to sitelinks. A leaf the cache does not know fails the build:
    a leaf with no fame cannot be cut, and the slider needs every one."""
    out, missing = {}, []
    for leaf in taxo.get_species(staging):
        entry = species.get(leaf.get("qid") or "")
        if entry is None or "sitelinks" not in entry:
            missing.append(leaf["name"])
        else:
            out[leaf["name"]] = int(entry["sitelinks"])
    if missing:
        raise SystemExit(f"{len(missing)} leaves have no sitelinks in the species cache, "
                         f"e.g. {missing[:3]}: the cache and the tree are from different scrapes")
    return out


def convert(n: dict, fame: dict[str, int]) -> dict:
    kids = n.get("children") or []
    if not kids:
        out = node(n["name"], n.get("rank"), label=n.get("common_name") or n["name"], aliases=[n["name"]])
        out["fame"] = fame[n["name"]]
        return out
    common = n.get("common_name")
    aliases = [common] if common and common.lower() != n["name"].lower() else None
    return node(n["name"], n.get("rank"), children=[convert(c, fame) for c in kids], aliases=aliases)


def cut_order(tree: dict) -> dict[str, int]:
    """Leaf name to its place when the tree is cut: fame descending, then name
    ascending, which is the contract both engines cut by."""
    leaves = taxo.get_species(tree)
    ranked = sorted(leaves, key=lambda x: (-x["fame"], x["name"]))
    return {x["name"]: i for i, x in enumerate(ranked)}


def entry_points(tree: dict) -> dict[str, int]:
    """Every node name to the place of its most famous leaf: the node is in the
    tree cut to `n` exactly when this is under `n`."""
    place = cut_order(tree)
    out: dict[str, int] = {}

    def walk(n: dict) -> int:
        kids = n.get("children") or []
        best = place[n["name"]] if not kids else min(walk(c) for c in kids)
        out[n["name"]] = best
        return best

    walk(tree)
    return out


def tiers(tree: dict, info: dict[str, dict], stops: list[int]) -> dict[int, dict[str, dict]]:
    """Popup text split by the stop at which each node enters. The last tier is
    the leaf count, so every node lands in one."""
    count = len(taxo.get_species(tree))
    bounds = sorted({*(s for s in stops if s < count), count})
    out: dict[int, dict[str, dict]] = {b: {} for b in bounds}
    for name, first in entry_points(tree).items():
        if name in info:
            out[next(b for b in bounds if first < b)][name] = info[name]
    return out


def popup_text(staging_info: dict[str, dict]) -> dict[str, dict]:
    """TaxoQuiz's taxon_info in TreeQuiz's fields. An entry with neither text
    nor picture is a fetch that found nothing, so it is left out: the popup
    says as much without it."""
    useful = {k: v for k, v in staging_info.items() if v.get("description") or v.get("image_url")}
    out = convert_info(useful)
    for entry in out.values():
        if entry.get("image_url", "").endswith(UTM):
            entry["image_url"] = entry["image_url"][: -len(UTM)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--taxoquiz", type=Path, default=REPO.parent / "TaxoQuiz",
                    help="a TaxoQuiz checkout to seed an empty work directory from")
    ap.add_argument("--dataset", default=None, help="staging tree (default: $ANIMALS_FULL_DATASET, else game)")
    args = ap.parse_args()
    name = args.dataset or taxo.current_dataset()

    seed(args.taxoquiz, name)
    staging = taxo.load_tree(taxo.tree_path(name))
    species_path = taxo.cache_dir() / taxo.CACHE_SPECIES
    if not species_path.is_file():
        raise SystemExit(f"{species_path} is missing: it holds every species' sitelinks. "
                         f"Seed it with --taxoquiz, or run datagen/animals_full/scraper.py")
    tree = convert(staging, fame_of(staging, read_json(species_path)))

    info_path = taxo.taxon_info_read_path(name)
    info = popup_text(read_json(info_path)) if info_path else {}
    if not info:
        print("note: no popup text for this staging tree; run datagen/animals_full/scrape_taxon_info.py")

    stops = read_json(OUT / "manifest.json")["sizes"]["stops"]
    split = tiers(tree, info, stops)

    write_dataset(DATASET, tree)
    # Tiers from an earlier build at other stops would be read as current.
    for old in [*OUT.glob("info-*.json"), OUT / "info.json"]:
        if old.exists() and old.name not in {f"info-{b}.json" for b in split}:
            old.unlink()
    for bound, part in split.items():
        write_json_atomic(OUT / f"info-{bound}.json", part, indent=None)
    print("popup text: " + ", ".join(f"info-{b}.json {len(p):,}" for b, p in split.items()))


if __name__ == "__main__":
    main()
