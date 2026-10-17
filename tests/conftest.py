"""Shared fixtures. Caches are cleared around every test, because they key on
the tree object and a dataset id, and two tests that write different trees
under one id would otherwise share the first one's."""
from __future__ import annotations

import json

import pytest

from treequiz import dataset, explore, game, lineup, odd


@pytest.fixture(autouse=True)
def _fresh_caches():
    dataset.clear_cache()
    game.clear_cache()
    explore.clear_cache()
    odd.clear_cache()
    lineup.clear_cache()
    yield
    dataset.clear_cache()
    game.clear_cache()
    explore.clear_cache()
    odd.clear_cache()
    lineup.clear_cache()


def n(name, rank=None, *children, **extra) -> dict:
    """A tree node, for writing fixtures compactly."""
    out = {"name": name, **extra}
    if rank is not None:
        out["rank"] = rank
    if children:
        out["children"] = list(children)
    return out


# A small tree with every shape the game cares about: a deep chain, a bushy
# genus, an unranked clade, labels that differ from names, and an alias.
ZOO = n("Animalia", "kingdom",
        n("Chordata", "phylum",
          n("Mammalia", "class",
            n("Carnivora", "order",
              n("Felidae", "family",
                n("Panthera", "genus",
                  n("Panthera leo", "species", label="lion", aliases=["Panthera leo"]),
                  n("Panthera tigris", "species", label="tiger"),
                  n("Panthera pardus", "species", label="leopard")),
                n("Felis", "genus", n("Felis catus", "species", label="domestic cat"))),
              n("Canidae", "family", n("Canis", "genus", n("Canis lupus", "species", label="grey wolf")))),
            n("Primates", "order", n("Homo", "genus", n("Homo sapiens", "species", label="human")))),
          n("Aves", "class", n("Passer", "genus", n("Passer domesticus", "species", label="house sparrow")))),
        n("Cnidaria", "phylum", n("Clade X", None, n("Aurelia aurita", "species", label="moon jelly"))))

ZOO_LADDER = {"levels": {"kingdom": 0, "phylum": 1, "class": 2, "order": 3, "family": 4, "genus": 5, "species": 6}, "top": 6}


@pytest.fixture
def zoo() -> dataset.Dataset:
    return dataset.from_tree(ZOO, {"title": "Zoo", "noun": "animal", "ladder": ZOO_LADDER}, "zoo")


@pytest.fixture
def datasets_dir(tmp_path, monkeypatch):
    """An empty datasets root, with a helper to write a dataset into it."""
    monkeypatch.setenv(dataset.DATASETS_ENV, str(tmp_path))

    def write(ds_id: str, tree: dict, manifest: dict | None = None, info: dict | None = None):
        d = tmp_path / ds_id
        d.mkdir()
        (d / "manifest.json").write_text(json.dumps(manifest or {"title": ds_id}))
        (d / "tree.json").write_text(json.dumps(tree))
        if info is not None:
            (d / "info.json").write_text(json.dumps(info))
        return d

    return write
