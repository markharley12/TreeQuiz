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


# --- instruments -----------------------------------------------------------

import build_instruments as bi  # noqa: E402

LIST = """\
==Membranophones (2)==
{{main|Membranophone}}
Drums, mostly.

===Struck membranophones (21)===
211.2 Instruments in which the body is tubular ([[tubular drum]]s)

211.212 Instruments which have two usable membranes
*[[Snare drum]]
* 111.242 [[Bell]]s – The vibration is weakest near the vertex.
*** (422.112 With conical bore.)
1914 was the year it was published.
"""


def test_a_class_list_reads_headings_bullets_and_bare_code_lines():
    got = bi.parse_classes(LIST)
    assert got["2"] == {"name": "Membranophones", "gloss": "Drums, mostly.", "link": "Membranophone"}
    assert got["2112"]["link"] == "tubular drum"
    assert got["211212"]["name"] == "Instruments which have two usable membranes"
    assert got["111242"] == {"name": "Bells", "gloss": "The vibration is weakest near the vertex.", "link": "Bell"}
    assert got["422112"]["name"] == "With conical bore", "a bracketed line keeps its code"
    assert got["1914"]["name"] == "was the year it was published", "which is why `only` exists"
    assert "1914" not in bi.parse_classes(LIST, only="2") and "111242" not in bi.parse_classes(LIST, only="2")


@pytest.mark.parametrize("raw,tidy", [
    ("Instruments in which the body is tubular (tubular drums)", "Tubular drums"),
    ("Instruments in which the body is conical-shaped (conical drums", "Conical drums"),
    ("Concussion sticks or stick clappers (clapstick)", "Concussion sticks or stick clappers"),
    ("(Single) oboes", "Single oboes"),
    ("Shaken Idiophones or rattles", "Shaken idiophones or rattles"),
    ("Instruments having electric action (e.g. pipe organ with solenoids);", "Instruments having electric action"),
])
def test_class_names_are_tidied_to_read_out_of_context(raw, tidy):
    assert bi.tidy(raw) == tidy


@pytest.mark.parametrize("code,parsed", [
    ("321.322-71", ("321322", "71")),
    ("314.122-4-8", ("314122", "4")),
    ("421.222.11+421.222.3+412.1", ("42122211", "")),
    ("211.311", ("211311", "")),
])
def test_a_code_is_read_as_its_digits_and_first_suffix(code, parsed):
    assert bi.parse_code(code) == parsed


def item(qid, label, codes, sitelinks=50, enwiki="", aliases=()):
    return {"qid": qid, "label": label, "codes": set(codes), "sitelinks": sitelinks,
            "enwiki": enwiki, "aliases": list(aliases)}


CLASSES = {d: {"name": n, "gloss": "", "link": "", "label": n} for d, n in {
    "1": "Idiophones", "11": "Struck idiophones", "112": "Indirectly struck", "1121": "Rattles",
    "3": "Chordophones", "32": "Composite chordophones", "321": "Lutes", "322": "Harps",
    "32132": "Necked lutes", "321321": "Necked bowl lutes", "321322": "Necked box lutes",
    "2": "Membranophones", "211": "Directly struck membranophones", "211311": "Frame drums",
}.items()}


def test_an_item_is_filed_under_its_most_specific_code_and_categories_are_left_out():
    chosen = {it["qid"]: it for it in bi.choose([
        item("Qtamb", "tambourine", ["112.1", "211.311"]),
        item("Qdrum", "drum", ["21"]),
        item("Qrare", "rare lute", ["321.321"], sitelinks=3),
        item("Q180744", "brass instrument", ["423"]),
    ], CLASSES, min_sitelinks=12)}
    assert set(chosen) == {"Qtamb"}
    assert chosen["Qtamb"]["digits"] == "211311"


def test_a_corrected_code_beats_the_one_wikidata_holds():
    [bayan] = bi.choose([item("Q804099", "bayan", ["421.221-12"])], {**CLASSES, "4": CLASSES["1"]}, 12)
    assert bayan["code"] == "412.132"


def test_leaf_names_take_diacritics_from_the_article_and_drop_aliases_that_name_another_leaf():
    chosen = [
        {**item("Qg", "gender", [], enwiki="https://en.wikipedia.org/wiki/Gend%C3%A8r"), "code": "111.222"},
        {**item("Qv", "violin", [], aliases=["fiddle", "violino"]), "code": "321.322-71"},
        {**item("Qf", "fiddle", []), "code": "321.322-71"},
        {**item("Qk", "kayagum", [], enwiki="https://en.wikipedia.org/wiki/Gayageum"), "code": "312.22-5"},
    ]
    bi.leaf_names(chosen)
    g, v, _, k = chosen
    assert g["name"] == "Gendèr"
    assert v["alias_list"] == ["violino", "321.322-71"]
    assert k["name"] == "kayagum" and k["alias_list"][0] == "Gayageum"


def test_the_same_label_twice_is_told_apart_by_code():
    chosen = [{**item("Qa", "cuatro", []), "code": "321.322-5"}, {**item("Qb", "Cuatro", []), "code": "321.321-6"}]
    bi.leaf_names(chosen)
    assert [c["name"] for c in chosen] == ["cuatro (321.322-5)", "Cuatro (321.321-6)"]


def build(items, classes=CLASSES, monkeypatch=None):
    monkeypatch.setattr(bi, "summaries", lambda titles: {})
    suffixes = {"3": {k: k for k in bi.SUFFIXES["3"]}, "2": {k: k for k in bi.SUFFIXES["2"]}}
    return bi.build(classes, suffixes, items, 1)


def test_bowing_is_a_group_below_the_lutes_so_a_violin_is_nearest_a_cello(monkeypatch):
    tree, _ = build([
        item("Qviolin", "violin", ["321.322-71"]), item("Qcello", "cello", ["321.322-71"]),
        item("Qguitar", "guitar", ["321.322-5"]), item("Qukulele", "ukulele", ["321.322-5"]),
        item("Qsitar", "sitar", ["321.321-6"]), item("Qharp", "harp", ["322"]),
        item("Qrattle", "rattle", ["112.1"]),
    ], monkeypatch=monkeypatch)
    lutes = tree["children"][1]["children"][0]["children"][0]
    assert lutes["label"] == "Necked lutes", "pass-throughs (Lutes, Composite chordophones' only lute) are spliced"
    box = next(c for c in lutes["children"] if c["label"] == "Necked box lutes")
    assert [(c["label"], c["rank"]) for c in box["children"]] == [("Plucked with fingers", "Played"), ("Bowed with a bow", "Played")]
    assert [c["label"] for c in box["children"][1]["children"]] == ["cello", "violin"]


def test_a_class_name_that_only_reads_under_its_parent_stops_the_build(monkeypatch):
    classes = {**CLASSES, "2113": {"name": "With handle", "gloss": "", "link": "", "label": "With handle"}}
    with pytest.raises(SystemExit, match=r"211\.3: 'With handle'"):
        build([item("Qa", "a", ["211.31"]), item("Qb", "b", ["211.32"])], classes, monkeypatch)


def test_a_class_link_must_land_on_an_article_about_the_class():
    assert bi.about("Frame drums", "Frame drum")
    assert bi.about("Simple chordophones or zithers", "Zither")
    assert not bi.about("Tubular drums", "Membranophone"), "a redirect that lands wide"
    assert not bi.about("Edge-blown aerophones or flutes", "List of musical instruments by Hornbostel–Sachs number")
