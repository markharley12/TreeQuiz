"""build_animals_full.py: a staging tree into TreeQuiz's shape, a fame on every
leaf, and the popup text split by when each node enters the cut tree."""
from __future__ import annotations

import json

import pytest

import build_animals_full as build
import conformance
from treequiz import dataset


def sp(name, common, qid):
    return {"name": name, "rank": "Species", "common_name": common, "scientific_name": name, "qid": qid}


# A staging tree, as extract_game_tree.py writes it: binomials as names, the
# English one beside, Q-IDs everywhere, and a vernacular on a famous clade.
STAGING = {
    "name": "Animalia", "rank": "Kingdom", "qid": "Q729", "common_name": "animal", "children": [
        {"name": "Felidae", "rank": "Family", "qid": "Q25265", "children": [
            sp("Panthera leo", "Lion", "Q140"),
            sp("Panthera tigris", "Tiger", "Q19939"),
            sp("Felis catus", "Cat", "Q146"),
        ]},
        {"name": "Aves", "rank": "Class", "qid": "Q5113", "common_name": "bird", "children": [
            sp("Passer domesticus", "House sparrow", "Q9325"),
            sp("Apteryx haastii", "Great spotted kiwi", "Q1361"),
        ]},
    ],
}
SITELINKS = {"Q140": 270, "Q19939": 250, "Q146": 300, "Q9325": 150, "Q1361": 40}
SPECIES = {q: {"sitelinks": s} for q, s in SITELINKS.items()}


def converted():
    return build.convert(STAGING, build.fame_of(STAGING, SPECIES))


def test_a_species_is_guessed_by_its_english_name_and_found_by_its_binomial():
    lion = converted()["children"][0]["children"][0]
    assert lion == {"name": "Panthera leo", "label": "Lion", "rank": "Species",
                    "aliases": ["Panthera leo"], "fame": 270}


def test_a_taxon_keeps_its_vernacular_as_an_alias_and_no_qid():
    tree = converted()
    assert tree["aliases"] == ["animal"]
    aves = tree["children"][1]
    assert aves["aliases"] == ["bird"] and "qid" not in aves and "label" not in aves
    assert "aliases" not in tree["children"][0]


def test_a_leaf_with_no_sitelinks_fails_the_build():
    """A leaf with no fame cannot be cut, so the slider could never drop it."""
    with pytest.raises(SystemExit, match="Apteryx haastii"):
        build.fame_of(STAGING, {q: v for q, v in SPECIES.items() if q != "Q1361"})


def test_cut_order_is_fame_then_name():
    tree = converted()
    tree["children"][0]["children"][1]["fame"] = 270   # the tiger ties the lion
    order = build.cut_order(tree)
    assert sorted(order, key=order.get) == [
        "Felis catus", "Panthera leo", "Panthera tigris", "Passer domesticus", "Apteryx haastii"]


def test_a_node_enters_with_its_most_famous_leaf():
    entry = build.entry_points(converted())
    assert entry["Animalia"] == entry["Felidae"] == entry["Felis catus"] == 0
    assert entry["Aves"] == entry["Passer domesticus"] == 3
    assert entry["Apteryx haastii"] == 4


def test_every_node_with_text_lands_in_exactly_the_tier_it_enters_at():
    tree = converted()
    info = {name: {"description": name} for name in build.entry_points(tree)}
    split = build.tiers(tree, info, stops=[2, 4, 10])
    # Stops past the leaf count are dropped and the leaf count closes the list.
    assert list(split) == [2, 4, 5]
    assert set(split[2]) == {"Animalia", "Felidae", "Felis catus", "Panthera leo"}
    assert set(split[4]) == {"Panthera tigris", "Aves", "Passer domesticus"}
    assert set(split[5]) == {"Apteryx haastii"}
    assert sum(len(p) for p in split.values()) == len(info)


def test_popup_text_drops_empty_fetches_and_wikipedias_tracking_tag():
    out = build.popup_text({
        "Panthera leo": {"qid": "Q140", "description": "The lion.", "image_url": "https://x/Lion.jpg" + build.UTM,
                         "wikipedia_url": "https://en.wikipedia.org/wiki/Lion", "wikipedia_title": "Lion"},
        "Felidae": {"qid": "Q25265", "description": "", "image_url": "", "wikipedia_url": "", "wikipedia_title": ""},
    })
    assert out == {"Panthera leo": {"description": "The lion.", "image_url": "https://x/Lion.jpg",
                                    "url": "https://en.wikipedia.org/wiki/Lion", "url_title": "Lion on Wikipedia"}}


def test_the_conformance_file_leaves_out_remote_trees(datasets_dir):
    """A tree published as a release exists on the machine that built it and not
    in CI, so a conformance file that included it would be stale on one."""
    tree = {"name": "r", "children": [{"name": "a"}, {"name": "b"}]}
    datasets_dir("here", tree)
    datasets_dir("there", tree, {"title": "There", "release": "there-2026-10-17"})
    assert dataset.available() == ["here", "there"]
    assert conformance.shipped() == ["here"]


def test_the_shipped_manifest_sizes_a_tree_it_can_cut():
    manifest = json.loads((build.OUT / "manifest.json").read_text())
    sizes = manifest["sizes"]
    assert sizes["stops"] == sorted(sizes["stops"]) and sizes["min"] == sizes["stops"][0]
    assert sizes["default"] in sizes["stops"]
    assert manifest["release"].startswith(f"{build.DATASET}-")
