"""The shipped datasets, checked as data — and the checks shown to bite.

Every other test checks code against a fixture it wrote. This one runs the
validator over what the app actually ships, which is the only place a tree that
is internally consistent and still wrong can be caught.
"""
from __future__ import annotations

import pytest
from conftest import ZOO, ZOO_LADDER, n

from treequiz import dataset
from treequiz.validate import validate

SHIPPED = dataset.available()


def test_there_are_datasets_to_ship():
    assert {"animals", "maths"} <= set(SHIPPED)


@pytest.mark.parametrize("ds_id", SHIPPED)
def test_shipped_dataset_is_fit_to_play(ds_id):
    report = validate(dataset.load(ds_id))
    assert report.ok, report.render()


@pytest.mark.parametrize("ds_id", SHIPPED)
def test_shipped_manifest_says_what_the_app_needs(ds_id):
    m = dataset.load(ds_id).manifest
    for key in ("title", "short_title", "prompt", "blurb", "noun", "noun_plural", "sources"):
        assert m.get(key), f"{ds_id} manifest lacks {key}"
    for source in m["sources"]:
        assert source.get("name") and source.get("url")
    assert 0 < float(m.get("bulk_unlock", 0.5)) <= 1


@pytest.mark.parametrize("ds_id", SHIPPED)
def test_info_is_keyed_by_names_the_tree_holds(ds_id):
    # Popup text keyed by a name that is not in the tree is stranded: it can
    # never be shown, and usually means a rename the builder missed.
    ds = dataset.load(ds_id)
    names = set()

    def walk(node):
        names.add(node["name"])
        for c in node.get("children") or []:
            walk(c)

    walk(ds.tree)
    stranded = sorted(set(ds.info) - names)
    assert not stranded, stranded[:5]


def zoo_with(tree=None, **manifest):
    return dataset.from_tree(tree or ZOO, {"title": "Zoo", "ladder": ZOO_LADDER, **manifest}, "zoo")


def test_the_validator_passes_a_good_tree():
    assert validate(zoo_with()).ok


def test_the_validator_fails_a_duplicate_name():
    tree = n("root", None, n("a", None, n("x")), n("b", None, n("x", label="other")))
    assert any("duplicate node names" in f for f in validate(zoo_with(tree)).failures)


def test_the_validator_fails_labels_that_differ_only_in_case():
    tree = n("root", None, n("a", label="Pacific lamprey"), n("b", label="Pacific Lamprey"))
    assert any("collide ignoring case" in f for f in validate(zoo_with(tree)).failures)


def test_the_validator_fails_an_empty_children_list():
    tree = n("root", None, n("a"), {"name": "b", "children": []})
    assert any("empty children" in f for f in validate(zoo_with(tree)).failures)


def test_the_validator_fails_an_epidemic_of_bad_ranks():
    # Every family claims to sit above its order.
    tree = n("root", "kingdom", *[
        n(f"o{i}", "order", n(f"f{i}", "phylum", n(f"s{i}", "species"))) for i in range(5)
    ])
    assert any("rank claims rejected" in f for f in validate(zoo_with(tree)).failures)


def test_the_validator_catches_a_flat_tree_by_its_orderings():
    # TaxoQuiz's bug: internally consistent, and a lion as close to a jellyfish
    # as to a tiger.
    flat = n("Animalia", "kingdom", *[
        n(name, "species", label=label) for name, label in
        [("Panthera leo", "lion"), ("Panthera tigris", "tiger"), ("Aurelia aurita", "moon jelly")]
    ])
    checks = {"closer": [{"to": "Panthera leo", "order": ["Panthera tigris", "Aurelia aurita"]}]}
    report = validate(zoo_with(flat, checks=checks))
    assert any("should beat" in f for f in report.failures)
    assert validate(zoo_with(checks=checks)).ok


def test_loading_an_unknown_dataset_names_the_ones_there_are(datasets_dir):
    datasets_dir("real", n("r", None, n("a"), n("b")))
    with pytest.raises(ValueError, match="real"):
        dataset.load("imaginary")
    assert dataset.available() == ["real"]
