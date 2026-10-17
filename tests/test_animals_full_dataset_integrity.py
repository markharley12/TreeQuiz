"""datagen/animals_full/validate_dataset.py: the checks a staging tree must pass.

Ported from TaxoQuiz's test_dataset_integrity.py. There it ran over the example
the game shipped; here the same 530-species tree is a test fixture,
`tests/fixtures/animals-530` (it shipped as `animals` until Oct 2026), converted back to the staging shape below, and TreeQuiz's own validator covers
the converted trees (tests/test_datasets.py). What stays is what a staging tree
can get wrong that a TreeQuiz tree cannot say: a leaf that is not a species, and
common names that collide.

The checks were wrong in TaxoQuiz before they were right — the scraper's
`RANK_LABELS` filed 355 beetle superfamilies as `Subkingdom`, and the example
went Animalia -> Phylum with nothing between — so each is shown to bite on a
deliberately broken tree.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "datagen" / "animals_full"))
import validate_dataset  # noqa: E402
from validate_dataset import check_biology, check_shape, check_warmth, validate  # noqa: E402


REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "animals-530"


@pytest.fixture
def example_tree():
    """TaxoQuiz's example, as `tests/fixtures/animals-530` holds it, in the staging shape:
    what is guessed is `common_name` there and `label` here."""
    def back(n):
        out = {k: v for k, v in n.items() if k not in ("label", "aliases", "children")}
        if n.get("children"):
            out["children"] = [back(c) for c in n["children"]]
        else:
            out["common_name"] = n.get("label", n["name"])
        return out
    return back(json.loads((FIXTURE / "tree.json").read_text()))


def node(name, rank, *children):
    n = {"name": name, "rank": rank}
    if children:
        n["children"] = list(children)
    return n


# --------------------------------------------------------------------------
# The dataset that ships
# --------------------------------------------------------------------------

def test_the_packaged_example_passes_every_check(example_tree):
    """The one that would have caught the flat tree, and the whole point of the
    file: it runs against what a fresh clone plays on."""
    # Held to its own manifest's orderings: animals (Wikidata's) adds two (a sparrow
    # nearer a pigeon than an ostrich, a salmon nearer a coelacanth than a
    # shark) that the curated tree is too coarse to pass, having no
    # Neognathae and no Osteichthyes.
    chains = validate_dataset.ground_truth(FIXTURE / "manifest.json")
    report = validate(example_tree, "example",
                      checks=(check_shape, check_warmth, lambda t, r: check_biology(t, r, chains)))
    assert report.ok, report.failures


def test_the_example_rejects_no_rank_claim_at_all(example_tree):
    """The early-warning number.

    `believed_levels` can survive bad ranks, which means a dataset can rot
    quietly. The hand-curated fixture should never need that mercy — a rejection
    appearing here means an edit put a rank somewhere it does not belong.
    """
    report = validate(example_tree, "example", checks=(check_warmth,))
    assert report.ok
    assert any("0 of" in n for n in report.notes), report.notes


# --------------------------------------------------------------------------
# Mutations — each turns one check red
# --------------------------------------------------------------------------

def test_a_flat_tree_fails_the_biology_check():
    """The original bug, in miniature: two phyla hung straight off the kingdom.

    A human and a starfish then share only the kingdom, exactly as a human and a
    sponge do, and no ordering can tell them apart.
    """
    flat = node("Animalia", "Kingdom",
                node("Chordata", "Phylum", node("Homo sapiens", "Species")),
                node("Echinodermata", "Phylum", node("Asterias rubens", "Species")),
                node("Porifera", "Phylum", node("Desmacella annexa", "Species")))
    report = validate(flat, "flat", checks=(check_biology,))
    assert not report.ok
    assert any("Asterias rubens" in f for f in report.failures), report.failures


def test_the_same_tree_passes_once_the_clade_layer_is_there():
    """And the fix, so the test above is not merely hard to satisfy."""
    deep = node("Animalia", "Kingdom",
                node("Porifera", "Phylum", node("Desmacella annexa", "Species")),
                node("Bilateria", "Clade",
                     node("Deuterostomia", "Clade",
                          node("Chordata", "Phylum", node("Homo sapiens", "Species")),
                          node("Echinodermata", "Phylum", node("Asterias rubens", "Species")))))
    assert validate(deep, "deep", checks=(check_biology,)).ok


def test_a_duplicate_name_fails_the_shape_check():
    """The game keys its depth index on the name, so a duplicate corrupts play
    silently rather than raising anywhere."""
    dupe = node("Animalia", "Kingdom",
                node("Gnathostomata", "Clade", node("a", "Species")),
                node("Gnathostomata", "Superfamily", node("b", "Species")))
    report = validate(dupe, "dupe", checks=(check_shape,))
    assert not report.ok
    assert "duplicate" in report.failures[0]


def test_a_rank_rot_epidemic_fails_the_warmth_check():
    """One bad rank is survivable and is meant to be; a tree full of them is a
    broken source, and the share is what says which you have.

    Measured: the scrape from before the `RANK_LABELS` repair rejects 6.5% of
    its rank claims, the repaired one 0.3%, the example 0%. The check fails
    above 5%, so the first of those is a dataset to rebuild and the second is a
    dataset to play.
    """
    # every family here contains an order, so both claims in each pair go
    rotten = node("Animalia", "Kingdom", *[
        node(f"fam{i}", "Family",
             node(f"ord{i}", "Order", node(f"sp{i}", "Species")))
        for i in range(20)
    ])
    report = validate(rotten, "rotten", checks=(check_warmth,))
    assert not report.ok
    assert "rejected" in report.failures[0], report.failures

    # and a single bad pair in an otherwise sound tree is a note, not a failure
    mostly_fine = node("Animalia", "Kingdom", *[
        node(f"ord{i}", "Order",
             node(f"fam{i}", "Family", node(f"sp{i}", "Species")))
        for i in range(40)
    ])
    mostly_fine["children"][0]["rank"] = "Family"
    mostly_fine["children"][0]["children"][0]["rank"] = "Order"
    ok = validate(mostly_fine, "mostly-fine", checks=(check_warmth,))
    assert ok.ok, ok.failures


def test_warmth_never_runs_backwards_however_bad_the_ranks_are():
    """The invariant the colour scale needs, and the one thing that must hold
    even on a dataset the checks above would reject outright."""
    absurd = node("Animalia", "Kingdom",
                  node("Suborder-of-everything", "Suborder",
                       node("Chordata", "Phylum",
                            node("Mammalia", "Class",
                                 node("Homo sapiens", "Species")))))
    report = validate(absurd, "absurd", checks=(check_warmth,))
    assert not any("inversion" in f for f in report.failures), report.failures


@pytest.mark.parametrize("chain", [c for _, c in validate_dataset.ground_truth()])
def test_every_ground_truth_species_is_named_by_its_scientific_name(chain):
    """Vernacular names differ between datasets — the example's "common
    starfish" is the scrape's "Common sea star" — so a chain written in them
    would silently skip every pair on one of the two."""
    for name in chain:
        assert name[0].isupper() and " " in name, name


def test_a_leaf_that_is_not_a_species_fails_the_shape_check():
    """A leaf is a guessable animal, so a clade with nothing under it is a fake one.

    Regression: this was a note rather than a failure, and the Sep 2026 rebuild
    shipped 189 childless clades as species — Apo-Chiroptera, a bat photograph
    labelled "Species", sat beside the real bats as a dead end.
    """
    fake = node("Mammalia", "Class",
                node("Chiroptera", "Order", node("Desmodus rotundus", "Species")),
                node("Apo-Chiroptera", "Clade"))
    report = validate(fake, "fake", checks=(check_shape,))
    assert not report.ok
    assert any("not species" in failure for failure in report.failures)


def test_common_names_colliding_ignoring_case_fail_the_shape_check():
    """The game looks a guess up by its common name, and the frontend capitalises
    on display, so "Pacific Lamprey" and "Pacific lamprey" are one choice shown
    twice to a player — 118 such pairs reached the Sep 2026 rebuild."""
    tree = node("Petromyzontidae", "Family",
                {"name": "Lampetra tridentata", "rank": "Species", "common_name": "Pacific Lamprey"},
                {"name": "Entosphenus tridentatus", "rank": "Species", "common_name": "Pacific lamprey"})
    report = validate(tree, "clash", checks=(check_shape,))
    assert any("collide ignoring case" in failure for failure in report.failures)
