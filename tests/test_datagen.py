"""The builders' own logic — the parts that do not need the network."""
from __future__ import annotations

import pytest

import build_maths
from common import collapse_lone_children
from conftest import n
from import_tree import parse_csv, parse_outline


OUTLINE = """\
# a comment
Mathematics
  Algebra | Branch
    Group theory | Subject | groups, group
    Ring theory | Subject

  Analysis | Branch
    Real analysis | Subject
    Complex <complex-analysis> | Subject
"""


def test_an_outline_becomes_a_tree():
    tree = parse_outline(OUTLINE)
    assert tree["name"] == "Mathematics"
    algebra, analysis = tree["children"]
    assert algebra["rank"] == "Branch"
    assert algebra["children"][0] == {"name": "Group theory", "rank": "Subject", "aliases": ["groups", "group"]}
    assert analysis["children"][1] == {"name": "complex-analysis", "label": "Complex", "rank": "Subject"}


def test_tabs_work_as_well_as_spaces():
    assert parse_outline("Root\n\tA\n\t\tA1\n\tB")["children"][0]["children"][0]["name"] == "A1"


@pytest.mark.parametrize("text,message", [
    ("Root\n  A\n  A", "used twice"),
    ("Root\nOther", "second root"),
    ("Root\n  A\n      Too deep", "more than one level"),
    ("  Indented\n", "before any root"),
    ("Root\n  A\n\tB", "indentation"),
    ("", "empty"),
])
def test_an_ambiguous_outline_is_refused_with_its_line(text, message):
    with pytest.raises(ValueError, match=message):
        parse_outline(text)


def test_a_csv_of_edges_becomes_a_tree_in_any_row_order():
    text = "name,parent,label,rank,aliases\nb1,b,,Leaf,\nroot,,Everything,,\nb,root,Bee,Group,bees;apis\na,root,,,\n"
    tree = parse_csv(text)
    assert tree["label"] == "Everything"
    assert [c["name"] for c in tree["children"]] == ["b", "a"]
    assert tree["children"][0]["aliases"] == ["bees", "apis"]
    assert tree["children"][0]["children"] == [{"name": "b1", "rank": "Leaf"}]


@pytest.mark.parametrize("text,message", [
    ("name,parent\na,\nb,\n", "exactly one row"),
    ("name,parent\na,\nb,ghost\n", "no row of their own"),
    ("name,parent\na,\nb,c\nc,b\n", "not under the root"),
    ("name,parent\na,\na,\n", "twice"),
    ("label\nx\n", "header"),
])
def test_a_bad_csv_is_refused(text, message):
    with pytest.raises(ValueError, match=message):
        parse_csv(text)


def test_lone_children_are_spliced_out_but_not_the_root_or_kept_ones():
    tree = n("root", None,
             n("chain", None, n("link", None, n("a"), n("b"))),
             n("fam", None, n("only")),
             n("solo", None, n("leaf")))
    out = collapse_lone_children(tree, keep={"fam"})
    assert [c["name"] for c in out["children"]] == ["link", "fam", "leaf"]
    assert out["children"][1]["children"] == [{"name": "only"}]


@pytest.mark.parametrize("tex,plain", [
    (r"\(K\)-theory", "K-theory"),
    (r"Grothendieck groups and \(K_0\)", "Grothendieck groups and K₀"),
    (r"Spin and Spin\({}^c\) geometry", "Spin and Spinᶜ geometry"),
    (r"\(n\)-ary systems \((n\ge 3)\)", "n-ary systems (n≥ 3)"),
    (r"Nonreal zeros of \(\zeta (s)\) and \(L(s, \chi)\)", "Nonreal zeros of ζ (s) and L(s, χ)"),
    (r"Fields over \(\mathbb{Q}\)", "Fields over ℚ"),
    (r"Automorphic forms on \(\mbox{GL}(2)\)", "Automorphic forms on GL(2)"),
])
def test_msc_tex_reads_as_plain_text(tex, plain):
    assert build_maths.detex(tex) == plain


def test_msc_names_lost_to_the_csvs_encoding_are_repaired():
    assert build_maths.repair("Randi? index; Erd?s problems; ?ech") == "Randić index; Erdős problems; Čech"


def test_msc_notes_drop_their_brackets():
    entry = {"text": "Graph theory", "description": "Graph theory {For computer science, see 68R10}"}
    assert build_maths.notes_of(entry) == "For computer science, see 68R10."
