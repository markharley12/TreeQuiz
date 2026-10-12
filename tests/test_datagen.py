"""The builders' own logic — the parts that do not need the network."""
from __future__ import annotations

import json

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


# --- chess -------------------------------------------------------------------

import build_chess as bc  # noqa: E402
from san import moves_of, play  # noqa: E402


def test_a_line_replays_to_its_position_and_remembers_the_last_move():
    pos = play(moves_of("1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"))
    assert pos.placement() == "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R"
    assert pos.last == ((0, 6), (0, 5))   # a7-a6


def test_castling_en_passant_and_a_pinned_knight_are_read_right():
    # Both knights reach e2, but the one on c3 is pinned by the bishop, so SAN
    # writes plain "Ne2" for the king's knight (the Winawer's Alekhine Gambit).
    pinned = play(moves_of("1. e4 e6 2. d4 d5 3. Nc3 Bb4 4. Ne2"))
    assert pinned.board[(4, 1)] == "N" and pinned.board[(2, 2)] == "N" and (6, 0) not in pinned.board
    castled = play(moves_of("1. e4 e5 2. Nf3 Nc6 3. Bb5 Nf6 4. O-O"))
    assert castled.board[(6, 0)] == "K" and castled.board[(5, 0)] == "R" and "K" not in "".join(castled.castling)
    ep = play(["e4", "Nf6", "e5", "d5", "exd6"])
    assert (3, 4) not in ep.board and ep.board[(3, 5)] == "P"


@pytest.mark.parametrize("moves", [["e5"], ["e4", "e4"], ["Nf3", "Nf6", "Nd5"], ["O-O"], ["Bb5"]])
def test_a_move_that_cannot_be_played_stops_the_build(moves):
    with pytest.raises(ValueError, match="move"):
        play(moves)


def test_a_segment_opens_on_blacks_move_with_an_ellipsis():
    moves = ["e4", "e6", "d4", "d5"]
    assert bc.segment(moves, 0) == "1.e4 e6 2.d4 d5"
    assert bc.segment(moves, 1) == "1…e6 2.d4 d5"
    assert bc.pgn(moves) == "1. e4 e6 2. d4 d5"


def line(name, pgn, eco="X00"):
    return {"name": name, "eco": eco, "moves": moves_of(pgn)}


def test_positions_are_merged_until_they_branch_and_an_opening_hangs_from_its_own():
    tree = bc.build([
        line("French Defense", "1. e4 e6"),
        line("French Defense: Advance Variation", "1. e4 e6 2. d4 d5 3. e5"),
        line("French Defense: Winawer Variation", "1. e4 e6 2. d4 d5 3. Nc3 Bb4"),
        line("French Defense: Classical Variation", "1. e4 e6 2. d4 d5 3. Nc3 Nf6"),
        line("Dutch Defense", "1. d4 f5"),
    ])
    e4, d4 = tree["children"]
    assert (e4["label"], d4["name"]) == ("1.e4 e6", "Dutch Defense")
    french = e4["children"]
    assert [c.get("label", c["name"]) for c in french] == ["French Defense", "2.d4 d5"]
    after_d5 = french[1]["children"]
    # 3.Nc3 holds two openings and stays a position; 3.e5 holds one and is it.
    assert [c.get("label", c["name"]) for c in after_d5] == ["3.Nc3", "French Defense: Advance Variation"]
    assert after_d5[0]["name"] == "1. e4 e6 2. d4 d5 3. Nc3"


def test_a_variation_is_kept_when_people_have_named_lines_under_it():
    best = {x["name"]: x for x in [
        line("Sicilian Defense", "1. e4 c5"),
        line("Sicilian Defense: Najdorf Variation", "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6"),
        line("Sicilian Defense: Najdorf Variation, Main Line", "1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 Nf6 5. Nc3 a6 6. Bg5"),
        line("Sicilian Defense: Obscure Variation", "1. e4 c5 2. a3"),
        line("London System, with Bd3", "1. d4 d5 2. Bf4 Nf6 3. Bd3"),
    ]}
    best.update({n: line(n, "1. e4") for n in bc.ALSO})
    kept = {x["name"] for x in bc.select(best)}
    assert {"Sicilian Defense", "Sicilian Defense: Najdorf Variation"} <= kept
    assert not kept & {"Sicilian Defense: Najdorf Variation, Main Line", "Sicilian Defense: Obscure Variation",
                       "London System, with Bd3"}


def test_an_articles_moves_are_read_from_its_lead():
    lead = "The Marshall Attack is a chess opening characterised by the moves:1. e4 e5\n2. Nf3 Nc6\n3. Bb5 a6\n5. 0-0 Be7 is"
    assert bc.article_line(lead) == ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "O-O", "Be7"]
    assert bc.article_line("Mikhail Chigorin was a Russian chess player.") == []


def summary(title, description):
    return {"title": title, "description": description, "url": f"https://en.wikipedia.org/wiki/{title}"}


def test_an_article_is_believed_only_when_it_is_about_this_opening(monkeypatch):
    pages = {
        "Sicilian Defence": summary("Sicilian Defence", "A chess opening: 1. e4 c5"),
        "Sicilian Defence, Najdorf Variation": summary(
            "Sicilian Defence, Najdorf Variation", "A variation of the Sicilian: 1. e4 c5 2. Nf3 d6"),
        # A redirect into the family's article, a person, and a set index.
        "Sicilian Defence, Kan Variation": summary("Sicilian Defence", "A chess opening: 1. e4 c5"),
        "Chigorin Variation": summary("Mikhail Chigorin", "Mikhail Chigorin was a Russian chess player."),
        "Taimanov Variation": summary("Taimanov Variation", "The Taimanov Variation can refer to several chess openings."),
        # Named right, wrong moves.
        "Four Knights Variation": summary("Four Knights Game", "A chess opening: 1. e4 e5 2. Nf3 Nc6 3. Nc3"),
    }
    monkeypatch.setattr(bc, "summaries", lambda titles: {t: pages.get(t) for t in titles})
    names = ["Sicilian Defense", "Sicilian Defense: Najdorf Variation", "Sicilian Defense: Kan Variation",
             "Queen's Pawn Game: Chigorin Variation", "Sicilian Defense: Taimanov Variation",
             "Sicilian Defense: Four Knights Variation"]
    lines = {"Sicilian Defense": ["e4", "c5"], "Sicilian Defense: Najdorf Variation": ["e4", "c5", "Nf3", "d6"],
             "Sicilian Defense: Four Knights Variation": ["e4", "c5", "Nf3", "e6"]}
    found = bc.wiki_for(names, lines)
    assert {n: s["title"] for n, s in found.items()} == {
        "Sicilian Defense": "Sicilian Defence",
        "Sicilian Defense: Najdorf Variation": "Sicilian Defence, Najdorf Variation",
    }


def test_a_board_is_a_small_svg_data_url():
    url = bc.data_url(bc.board_svg(play(["e4"])))
    assert url.startswith("data:image/svg+xml;charset=utf-8,<svg")
    assert "#" not in url and len(url) < 1600


def test_an_articles_move_list_is_folded_back_into_its_sentence():
    lead = ("The Najdorf Variation ( NY-dorf) is a variation that begins with the moves:\n\n"
            "1. e4 c5\n2. Nf3 d6\n5. 0-0 a6\nBlack's 5...a6 aims to deny b5.\nIt is popular.\n\n")
    assert bc.tidy_intro(lead) == (
        "The Najdorf Variation (NY-dorf) is a variation that begins with the moves "
        "1. e4 c5 2. Nf3 d6 5. O-O a6. Black's 5...a6 aims to deny b5.\nIt is popular.")


# --- physics -----------------------------------------------------------------

import build_physics as bph  # noqa: E402
from wikipedia import named_for  # noqa: E402


@pytest.mark.parametrize("label,title,same", [
    ("Black holes", "Black hole", True),
    ("Bose-Einstein condensates", "Bose–Einstein condensate", True),
    ("W & Z bosons", "W and Z bosons", True),
    ("Mergers", "Mergers and acquisitions", False),
    ("Quantum dots", "Quantum", False),
])
def test_a_title_names_a_label_give_or_take_a_plural_and_a_dash(label, title, same):
    assert named_for(label, title) is same


def test_a_redirect_is_believed_unless_it_broadens_lands_in_a_section_or_is_shared():
    pages = {
        "Gravitation": {"title": "Gravity", "qid": "Q1", "redirect": True, "fragment": None},
        "Vacuum technology": {"title": "Vacuum", "qid": "Q2", "redirect": True, "fragment": None},
        "Classical optics": {"title": "Optics", "qid": "Q3", "redirect": True, "fragment": "Classical optics"},
        "Atomic spectra": {"title": "Spectroscopy", "qid": "Q4", "redirect": True, "fragment": None},
        "Molecular spectra": {"title": "Spectroscopy", "qid": "Q4", "redirect": True, "fragment": None},
        "Superconductors": {"title": "Superconductivity", "qid": "Q5", "redirect": True, "fragment": None},
        "Superconductivity": {"title": "Superconductivity", "qid": "Q5", "redirect": False, "fragment": None},
    }
    got = bph.accept_pages(list(pages), pages, {})
    assert {k: v["title"] for k, v in got.items()} == {"Gravitation": "Gravity", "Superconductivity": "Superconductivity"}


def concept(label, broader=(), facet=None, disciplines=()):
    return {"label": label, "aliases": [], "broader": list(broader), "facet": facet, "disciplines": list(disciplines)}


def test_a_concept_takes_its_deepest_parent_then_its_main_home_and_a_top_its_smallest_discipline():
    disciplines = {"d:amo": {"label": "Atomic, Molecular & Optical"}, "d:acc": {"label": "Accelerators & Beams"},
                   "d:x": {"label": "Plasma Physics"}}
    concepts = {
        "optics": concept("Optics & lasers", facet="Research Areas", disciplines=["d:amo"]),
        "beams": concept("Accelerator subsystems", facet="Research Areas", disciplines=["d:acc"]),
        "other": concept("Other optics", ["optics"]),
        "more": concept("More optics", ["optics"]),
        "lasers": concept("Lasers", ["optics", "beams"]),
        "mhd": concept("Magnetohydrodynamics", facet="Research Areas", disciplines=["d:amo", "d:x"]),
        "ai": concept("Artificial intelligence", ["optics"], facet="Computational Techniques", disciplines=["d:amo"]),
        "deep": concept("Deep learning", ["ai"]),
    }
    parent = bph.choose_parents(concepts, disciplines)
    assert parent["lasers"] == "optics"           # a tie on depth goes to more beneath
    assert parent["mhd"] == "d:x"                 # the discipline with fewer tops
    assert "ai" not in parent and "deep" not in parent   # a technique stays out


# --- chemistry -----------------------------------------------------------------

import build_chemistry as bch  # noqa: E402


def chebi():
    names = {"C:root": "chemical entity", "C:atom": "atom", "C:metal": "metal atom", "C:fe": "iron atom",
             "C:fe0": "iron(0)", "C:mol": "molecular entity", "C:gas": "gas molecular entity",
             "C:org": "organic molecular entity", "C:alk": "alkaloid", "C:xan": "methylxanthine",
             "C:caf": "caffeine", "C:theo": "theobromine", "C:allergen": "penicillin allergen", "C:pen": "penicillin",
             "C:benz": "benzylpenicillin", "C:wrong": "CU-O LINKAGE", "C:cuo": "copper(II) oxide"}
    parents = {"C:root": [], "C:atom": ["C:root"], "C:metal": ["C:atom"], "C:fe": ["C:metal"],
               "C:fe0": ["C:mol"], "C:mol": ["C:root"], "C:gas": ["C:mol"], "C:org": ["C:mol"],
               "C:alk": ["C:org"], "C:xan": ["C:alk"], "C:caf": ["C:xan", "C:gas"], "C:theo": ["C:xan"],
               "C:pen": ["C:org"], "C:allergen": ["C:pen"], "C:benz": ["C:allergen", "C:pen"],
               "C:wrong": ["C:org"], "C:cuo": ["C:mol"]}
    return names, parents


def test_an_element_is_its_atom_and_a_wrong_chebi_id_is_corrected(monkeypatch):
    names, parents = chebi()
    monkeypatch.setattr(bch, "ROOT", "C:root")
    monkeypatch.setattr(bch, "ATOM", "C:atom")
    monkeypatch.setattr(bch, "CHEBI_FIXES", {"Qcuo": "C:cuo"})
    items = {
        "Qfe": {"sitelinks": 200, "chebi": ["C:fe", "C:fe0"], "element": True, "inchikey": True, "title": "Iron"},
        "Qcuo": {"sitelinks": 50, "chebi": ["C:wrong"], "inchikey": True, "title": "Copper(II) oxide"},
        "Qalk": {"sitelinks": 90, "chebi": ["C:alk"], "inchikey": False, "title": "Alkaloid"},
    }
    chosen = bch.choose(items, names, parents, bch.depths(parents))
    assert set(chosen) == {"C:fe", "C:cuo"}       # the class has no structure, so no InChIKey


def test_a_chemical_hangs_from_its_structural_class_not_its_state_or_its_use(monkeypatch):
    names, parents = chebi()
    monkeypatch.setattr(bch, "ROOT", "C:root")
    depth = bch.depths(parents)
    chosen = {t: {"title": names[t].capitalize(), "qid": t} for t in ("C:caf", "C:theo", "C:benz", "C:fe")}
    tree, _ = bch.build(chosen, names, parents, depth)

    def path(n, name, above=()):
        if n["name"] == name:
            return list(above)
        for c in n.get("children") or []:
            found = path(c, name, (*above, n["name"]))
            if found is not None:
                return found
        return None

    assert "methylxanthine" in path(tree, "caffeine") and "gas molecular entity" not in path(tree, "caffeine")
    assert "penicillin allergen" not in path(tree, "benzylpenicillin")
    assert bch.label_of("Mercury (element)") == "Mercury"
    assert bch.label_of("Poly(methyl methacrylate)") == "Poly(methyl methacrylate)"


# --- cities --------------------------------------------------------------------

import build_cities as bcy  # noqa: E402

def country(name, continent, subregion, qid, iso, region_un=None):
    return {"properties": {"NAME": name, "CONTINENT": continent, "SUBREGION": subregion, "WIKIDATAID": qid,
                           "ISO_N3": iso, "REGION_UN": region_un or continent}}


def test_natural_earth_gives_continent_and_subregion_and_files_open_ocean_islands_by_the_un(monkeypatch, tmp_path):
    page = tmp_path / "countries.geojson"
    page.write_text(json.dumps({"features": [
        country("Burundi", "Africa", "Eastern Africa", "Q967", "108"),
        country("Brazil", "South America", "South America", "Q155", "076"),
        country("Maldives", "Seven seas (open ocean)", "Southern Asia", "Q826", "462", region_un="Asia"),
        country("Mauritius", "Seven seas (open ocean)", "Seven seas (open ocean)", "Q1027", "480", region_un="Africa"),
        country("S. Geo. and the Is.", "Seven seas (open ocean)", "South America", "Q35086", "239", region_un="Americas"),
        country("Kosovo", "Europe", "Southern Europe", "Q1246", "-99"),
    ]}))
    monkeypatch.setattr(bcy, "fetch", lambda *a, **k: page)
    regions, by_iso = bcy.natural_earth(False)
    assert regions["Q967"] == ["Africa", "Eastern Africa"]
    assert regions["Q155"] == ["South America"]            # no subregion but itself
    assert regions["Q826"] == ["Asia", "Southern Asia"]
    assert regions["Q1027"] == ["Africa"]
    assert "Q35086" not in regions                         # no continent to give
    assert by_iso == {"108": "Q967", "076": "Q155", "462": "Q826", "480": "Q1027"}


def test_a_city_counts_every_first_level_unit_above_it_but_dissolved_ones():
    graph = {"types": {"Tmetro": "metropolitan municipality in Turkey", "Tprov": "province of Turkey"},
             "up": {"Qist": ["Qprov", "Qottoman"], "Qprov": ["Qtr"], "Qottoman": ["Qtr"], "Qtr": []},
             "kinds": {"Qist": ["Tmetro", "Qcity"], "Qprov": ["Tprov"], "Qottoman": ["Tprov"], "Qtr": []},
             "gone": ["Qottoman"]}
    assert sorted(bcy.first_level("Qist", graph)) == [("Qist", "Tmetro", 0), ("Qprov", "Tprov", 1)]


def cities_data():
    regions = {"Qfr": ["Europe", "Western Europe"], "Qil": ["Asia", "Western Asia"],
               "Qne-ps": ["Asia", "Western Asia"], "Qsg": ["Asia", "South-Eastern Asia"], "Qus": ["North America", "Northern America"]}
    by_iso = {"250": "Qfr", "376": "Qil", "275": "Qne-ps", "702": "Qsg", "840": "Qus"}
    places = {"Qfr": {"title": "France", "codes": ["250"]}, "Qil": {"title": "Israel", "codes": ["376"]},
              "Qps": {"title": "State of Palestine", "codes": ["275"]}, "Qsg": {"title": "Singapore", "codes": ["702"]},
              "Qus": {"title": "United States", "codes": ["840"]}, "Qold": {"title": "Kingdom of France", "codes": []},
              "Qidf": {"title": "Île-de-France"}, "Qara": {"title": "Auvergne-Rhône-Alpes"},
              "Qdep": {"title": "Rhône (department)"}, "Qa": {"title": "Region A"}, "Qb": {"title": "Region B"},
              "Qny": {"title": "New York (state)"}}
    city = lambda title, countries, **kw: {"sitelinks": 200, "population": 100000, "capital": False,  # noqa: E731
                                           "title": title, "label": title, "countries": countries, **kw}
    cities = {"Qparis": city("Paris", ["Qfr", "Qold"]), "Qvers": city("Versailles", ["Qfr"]), "Qlyon": city("Lyon", ["Qfr"]),
              "Qnice": city("Nice", ["Qfr"]), "Qsplit": city("Splitville", ["Qfr"]),
              "Qjer": city("Jerusalem", ["Qil", "Qps"]), "Qsg": city("Singapore", ["Qsg"]),
              "Qnyc": city("New York City", ["Qus"]), "Qbk": city("Brooklyn", ["Qus"]), "Qbuf": city("Buffalo", ["Qus"]),
              "Qtroy": city("Troy", ["Qold"], population=None), "Qsmall": city("Hamlet", ["Qfr"], sitelinks=10)}
    graph = {"types": {"Treg": "region of France", "Tdep": "department of France", "Tst": "U.S. state"},
             "up": {"Qparis": ["Qidf"], "Qvers": ["Qidf"], "Qlyon": ["Qdep"], "Qdep": ["Qara"], "Qnice": ["Qa"],
                    "Qsplit": ["Qa", "Qb"], "Qnyc": ["Qny"], "Qbk": ["Qnyc"], "Qbuf": ["Qny"]},
             "kinds": {"Qidf": ["Treg"], "Qara": ["Treg"], "Qdep": ["Tdep"], "Qa": ["Treg"], "Qb": ["Treg"], "Qny": ["Tst"]},
             "gone": []}
    return {"cities": cities, "places": places, "graph": graph, "aliases": {}}, regions, by_iso


def test_cities_are_placed_by_country_and_their_countrys_usual_kind_of_region(monkeypatch):
    monkeypatch.setattr(bcy, "NOT_REGION", set())
    data, regions, by_iso = cities_data()
    chosen = {it["title"]: it for it in bcy.choose(data, regions, by_iso, 100)}
    assert set(chosen) == {"Paris", "Versailles", "Lyon", "Nice", "Splitville", "Jerusalem", "Singapore",
                           "New York City", "Buffalo"}
    assert chosen["Paris"]["country"] == "Qfr" and chosen["Paris"]["region"] == "Qidf"   # the kingdom is history
    assert chosen["Lyon"]["region"] == "Qara"          # regions outnumber departments in France
    assert chosen["Splitville"]["region"] is None      # in two regions at once: filed under the country
    assert chosen["Jerusalem"]["country"] is None and chosen["Jerusalem"]["chain"] == ["Asia", "Western Asia"]
    assert chosen["Singapore"]["city_state"] and chosen["Singapore"]["country"] is None


def test_a_place_inside_another_chosen_city_is_part_of_it_not_a_city(monkeypatch):
    monkeypatch.setattr(bcy, "NOT_REGION", set())
    data, regions, by_iso = cities_data()
    titles = {it["title"] for it in bcy.choose(data, regions, by_iso, 100)}
    assert "Brooklyn" not in titles and "New York City" in titles
    assert bcy.above("Qbk", data["graph"]) == {"Qnyc", "Qny"}


def test_a_small_town_is_kept_only_as_a_capital_or_a_city_state(monkeypatch):
    # Sitelinks can be made in bulk: a town of 6,500 had more than Seville.
    monkeypatch.setattr(bcy, "NOT_REGION", set())
    data, regions, by_iso = cities_data()
    data["cities"]["Qtown"] = {**data["cities"]["Qnice"], "title": "Monte Águila", "population": 6500}
    data["cities"]["Qvaduz"] = {**data["cities"]["Qnice"], "title": "Vaduz", "population": 5600, "capital": True}
    data["cities"]["Qsg"]["population"] = 900
    titles = {it["title"] for it in bcy.choose(data, regions, by_iso, 100)}
    assert "Monte Águila" not in titles
    assert {"Vaduz", "Singapore"} <= titles


def test_a_country_off_natural_earths_map_stops_the_build(monkeypatch):
    monkeypatch.setattr(bcy, "NOT_REGION", set())
    data, regions, by_iso = cities_data()
    data["cities"]["Qatl"] = {"sitelinks": 200, "population": 100000, "capital": False, "title": "Atlantis",
                              "label": "Atlantis", "countries": ["Qsea"]}
    with pytest.raises(SystemExit, match="Atlantis"):
        bcy.choose(data, regions, by_iso, 100)


def test_the_tree_runs_continent_subregion_country_region_city(monkeypatch):
    monkeypatch.setattr(bcy, "NOT_REGION", set())
    data, regions, by_iso = cities_data()
    tree, titles = bcy.build(data, regions, by_iso, 100)

    def find(n, name, above=()):
        if n["name"] == name:
            return n, list(above)
        for c in n.get("children") or []:
            if (hit := find(c, name, (*above, n.get("label", n["name"])))) is not None:
                return hit
        return None

    paris, above = find(tree, "Paris")
    assert above == ["World", "Europe", "Western Europe", "France", "Île-de-France"]
    assert find(tree, "France")[0]["rank"] == "Country" and find(tree, "Western Europe")[0]["rank"] == "Subregion"
    assert find(tree, "Jerusalem")[1] == ["World", "Asia", "Western Asia"]
    sg, above = find(tree, "Singapore")
    assert sg["rank"] == "City-state" and above == ["World", "Asia", "South-Eastern Asia"]
    assert find(tree, "Region A") is None              # Nice alone in it, so spliced out
    assert find(tree, "New York (state)")[0]["label"] == "New York"
    assert titles["Western Asia"] == "West Asia"       # the popup reads the article


def test_a_city_label_drops_what_its_lineage_says_unless_two_cities_would_share_it():
    places = {"Qus": {"title": "United States"}, "Qor": {"title": "Oregon"}, "Qal": {"title": "Alabama"},
              "Quk": {"title": "United Kingdom"}}
    chosen = [{"title": "Portland, Oregon", "country": "Qus", "region": "Qor"},
              {"title": "Birmingham", "country": "Quk", "region": None},
              {"title": "Birmingham, Alabama", "country": "Qus", "region": "Qal"},
              {"title": "Washington, D.C.", "country": "Qus", "region": None}]
    bcy.city_labels(chosen, places)
    assert [c["label"] for c in chosen] == ["Portland", "Birmingham", "Birmingham, Alabama", "Washington, D.C."]


def test_aliases_another_city_answers_to_are_dropped():
    chosen = [{"qid": "Q1", "label": "Mumbai", "title": "Mumbai"}, {"qid": "Q2", "label": "Saint Petersburg", "title": "Saint Petersburg"},
              {"qid": "Q3", "label": "Petersburg", "title": "Petersburg, Virginia"}]
    aliases = {"Q1": ["Bombay", "Mumbai"], "Q2": ["Petersburg", "St. Petersburg", "Leningrad"], "Q3": ["Leningrad"]}
    bcy.city_aliases(chosen, aliases, {})
    assert chosen[0]["aliases"] == ["Bombay"]
    assert chosen[1]["aliases"] == ["St. Petersburg"]          # Petersburg is a city; Leningrad is claimed twice
    assert chosen[2]["aliases"] == ["Petersburg, Virginia"]


@pytest.mark.parametrize("label,rank", [("federal subject of Russia", "Federal subject"), ("U.S. state", "State"),
                                        ("constituent country of the United Kingdom", "Constituent country"),
                                        ("metropolitan municipality in Turkey", "Metropolitan municipality")])
def test_a_region_type_becomes_a_short_rank(label, rank):
    assert bcy.type_rank(label) == rank
