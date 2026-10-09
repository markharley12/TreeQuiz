"""Build `datasets/physics`: fields and objects of physics, on PhySH.

PhySH, the Physics Subject Headings (https://physh.org), is how the American
Physical Society files its journals: about 3,900 concepts, CC0. It is to
physics what MSC2020 is to mathematics, with two differences that shape this
builder.

**It is faceted.** Each discipline (Condensed Matter, Plasma Physics, …) files
its concepts under facets: Research Areas ("Superconductivity"), Physical
Systems ("Black holes"), Properties, Techniques, Professional Topics. Only
the first two are kept. They are what a physicist studies; techniques are
how, and would make "Monte Carlo methods" a field of every discipline. The
facet itself is not a level of the tree: it is a filing category, and
sharing one would score as kinship between superconductivity and plasma
waves.

**It is a lattice, not a tree.** 223 concepts have two or more broader
concepts, and 34 top concepts are filed under two or three disciplines. One
parent is chosen for each:

* a concept goes under the broader concept with the **longest path to a top**,
  TaxoQuiz's rule for Wikidata's several parents, since where one candidate
  lies beneath another the deeper one is always the more specific (`Hadron
  colliders` under Colliders, not Particle accelerators). Between equally deep
  candidates the one with **more beneath it** wins, the concept's main home
  rather than a side door: Lasers go to Optics & lasers, not Accelerator
  subsystems, which alphabetical order had chosen;
* a top concept goes to the discipline with the **fewest top concepts**, the
  most specific home: Magnetohydrodynamics to Plasma Physics rather than Fluid
  Dynamics, Pattern formation to Nonlinear Dynamics rather than Statistical
  Physics. Ties go alphabetically.

**Which concepts.** A concept is famous when English Wikipedia has an article
named for it, and Wikidata says how many Wikipedias have one (`MIN_SITELINKS`).
Titles are not linked from PhySH, so a label is looked up as a title, and the
page it lands on must be named for it, give or take a plural and a dash:
"Black holes" lands on *Black hole*, but "Mergers" lands on *Mergers and
acquisitions* and is refused. Disambiguation pages are refused. The tree keeps
every famous concept and everything above one; a famous concept with famous
concepts beneath it is a group, not a leaf, as Panthera is in TaxoQuiz.

Left out: the APS Taxonomy (a scheme of schemes), General Physics (two
concepts), and Physics Education Research, which is about teaching.
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import urllib.parse
from collections import defaultdict

from common import CACHE, collapse_lone_children, fetch, node, write_dataset
from wikipedia import _fold, _forms, _get, info_entry, named_for, summaries

REF = "04b9cec3e633aa1abf68f2a09868fdc56be12e60"   # physh-org/PhySH, 2026-03-24
SOURCE = f"https://raw.githubusercontent.com/physh-org/PhySH/{REF}/physh.json.gz"
MIN_SITELINKS = 25
FACETS = {"Research Areas", "Physical Systems"}
LEFT_OUT = {"APS Taxonomy", "General Physics", "Physics Education Research", "Networks"}
# Its physical systems are biology's — DNA, enzymes, organs, sperm — so only its
# research areas (protein folding, biomechanics) come in.
SYSTEMS_LEFT_OUT = {"Physics of Living Systems"}
# Groups PhySH files for indexing that are applications or neighbours of
# physics rather than physics: paints and cosmetics, and economic games.
PRUNE = {"Applications of soft matter", "Social dynamics", "Engineering"}

# The disciplines' own articles, for their popups. Their names are the APS's
# and no article carries them.
DISCIPLINE_ARTICLES = {
    "Accelerators & Beams": "Accelerator physics",
    "Atomic, Molecular & Optical": "Atomic, molecular, and optical physics",
    "Condensed Matter, Materials & Applied Physics": "Condensed matter physics",
    "Energy Science & Technology": "Energy development",
    "Fluid Dynamics": "Fluid dynamics",
    "Gravitation, Cosmology & Astrophysics": "Astrophysics",
    "Interdisciplinary Physics": "Interdisciplinary physics",
    "Networks": "Network science",
    "Nonlinear Dynamics": "Nonlinear system",
    "Nuclear Physics": "Nuclear physics",
    "Particles & Fields": "Particle physics",
    "Physics of Living Systems": "Biophysics",
    "Plasma Physics": "Plasma (physics)",
    "Polymers & Soft Matter": "Soft matter",
    "Quantum Information, Science & Technology": "Quantum information science",
    "Statistical Physics & Thermodynamics": "Statistical mechanics",
}

# Labels no article is named for, and the article that is about them. Mostly
# PhySH's compounds, "X & Y". Taking a part by rule was tried and is wrong as
# often as right, since the parts can share a head word at either end:
# "Neutron stars & pulsars" is two things, "Earthquake detection &
# measurement" is earthquake measurement, not *Measurement*.
TITLES = {
    "Astronomical black holes": "Black hole",
    "Neutron stars & pulsars": "Neutron star",
    "Novae & supernovae": "Supernova",
    "Galactic nuclei & quasars": "Quasar",
    "Asteroids, meteors, & meteorites": "Asteroid",
    "Solar system & its planets": "Solar System",
    "Cosmic rays & astroparticles": "Cosmic ray",
    "Cosmic strings & domain walls": "Cosmic string",
    "Baryogenesis & leptogenesis": "Baryogenesis",
    "Planets & planetary systems": "Planetary system",
    "Electricity & lightning": "Lightning",
    "Synchrotron radiation & free-electron lasers": "Synchrotron radiation",
    "Photon pairs & parametric down-conversion": "Spontaneous parametric down-conversion",
    "Superradiance & subradiance": "Superradiance",
    "Fine & hyperfine structure": "Hyperfine structure",
    "Quasiparticles & collective excitations": "Quasiparticle",
    "Open quantum systems & decoherence": "Quantum decoherence",
    "Disclinations & dislocations": "Dislocation",
    "Surfactants, micelles & vesicles": "Surfactant",
    "Binding energy & masses": "Binding energy",
    "Isotope separation & enrichment": "Isotope separation",
}

# Redirects to the wrong page: PhySH's billiards are the dynamical systems,
# not the game; light-matter interaction is not all of optics, nor is membrane
# transport only active transport.
NOT_THE_SAME = {"Billiards", "Light-matter interaction", "Cell membrane transport"}

SKOS = "http://www.w3.org/2004/02/skos/core#"
PHYSH = "https://physh.org/rdf/2018/01/01/core#"


def _ids(x: dict, key: str) -> list[str]:
    return [y["@id"] for y in x.get(key, [])]


def _label(x: dict) -> str:
    return (x.get(SKOS + "prefLabel") or x[PHYSH + "prefLabel"])[0]["@value"]


def load(refresh: bool) -> list[dict]:
    path = fetch(SOURCE, CACHE / "physics" / f"physh-{REF[:8]}.json.gz", refresh=refresh)
    return json.load(gzip.open(path))


def read_scheme(items: list[dict]) -> tuple[dict[str, dict], dict[str, dict]]:
    """Concepts and disciplines by id. A concept: label, aliases, broader ids,
    and — for a top concept — its facet and disciplines."""
    by_id = {x["@id"]: x for x in items}
    disciplines = {x["@id"]: {"label": _label(x)} for x in items if PHYSH + "Discipline" in x["@type"]}
    concepts = {}
    for x in items:
        if PHYSH + "Discipline" in x["@type"] or PHYSH + "Facet" in x["@type"] or x.get(PHYSH + "deprecated"):
            continue
        facets = [_label(by_id[f]) for f in _ids(x, PHYSH + "inFacet")]
        concepts[x["@id"]] = {
            "label": _label(x),
            "aliases": [a["@value"] for a in x.get(SKOS + "altLabel", [])],
            "broader": _ids(x, SKOS + "broader"),
            "facet": facets[0] if facets else None,
            "disciplines": _ids(x, PHYSH + "inDiscipline"),
        }
    return concepts, disciplines


def choose_parents(concepts: dict[str, dict], disciplines: dict[str, dict]) -> dict[str, str]:
    """Each kept concept's one parent: a discipline id for a top concept, a
    concept id for the rest. Concepts not under a kept top are absent."""
    kept_disc = {d for d, v in disciplines.items() if v["label"] not in LEFT_OUT}

    def homes(c: str) -> list[str]:
        v = concepts[c]
        return [d for d in v["disciplines"] if d in kept_disc
                and not (v["facet"] == "Physical Systems" and disciplines[d]["label"] in SYSTEMS_LEFT_OUT)]

    tops = {c for c, v in concepts.items() if v["facet"] in FACETS and homes(c) and v["label"] not in PRUNE}
    # A technique stays out even where a research area also lists it beneath
    # itself: Artificial intelligence is a Computational Technique, and filed
    # under Quantum computation too, it brought deep learning with it.
    barred = {c for c, v in concepts.items() if (v["facet"] and v["facet"] not in FACETS) or v["label"] in PRUNE}
    narrower: dict[str, list[str]] = defaultdict(list)
    for c, v in concepts.items():
        for b in v["broader"]:
            narrower[b].append(c)

    # Everything reachable from a kept top, and each one's longest path to a top.
    reach: set[str] = set()
    stack = list(tops)
    while stack:
        c = stack.pop()
        if c in reach or c in barred:
            continue
        reach.add(c)
        stack.extend(narrower[c])
    depth: dict[str, int] = {}

    def longest(c: str, seen: frozenset = frozenset()) -> int:
        if c in depth:
            return depth[c]
        if c in tops:
            depth[c] = 0
            return 0
        best = max((longest(b, seen | {c}) + 1 for b in concepts[c]["broader"]
                    if b in reach and b not in seen), default=0)
        depth[c] = best
        return best

    sizes: dict[str, int] = {}

    def size(c: str) -> int:
        """Concepts beneath, each once."""
        if c not in sizes:
            seen, todo = set(), list(narrower[c])
            while todo:
                k = todo.pop()
                if k in reach and k not in seen:
                    seen.add(k)
                    todo.extend(narrower[k])
            sizes[c] = len(seen)
        return sizes[c]

    top_count = {d: sum(1 for t in tops if d in homes(t)) for d in kept_disc}
    parent = {}
    for c in sorted(reach):
        if c in tops:
            parent[c] = min(homes(c), key=lambda d: (top_count[d], disciplines[d]["label"]))
        else:
            cands = [b for b in concepts[c]["broader"] if b in reach]
            parent[c] = min(cands, key=lambda b: (-longest(b), -size(b), concepts[b]["label"]))
    return parent


# --- fame -------------------------------------------------------------------

def resolve_titles(labels: list[str], refresh: bool) -> dict[str, dict | None]:
    """Label to {title, qid} of the English Wikipedia page it lands on, or
    None: no page, a disambiguation page, or a page named for something
    else. Cached in `_cache/physics/titles.json`."""
    path = CACHE / "physics" / "titles.json"
    cache = {} if refresh or not path.exists() else json.loads(path.read_text())
    todo = [x for x in dict.fromkeys(labels) if x not in cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        q = urllib.parse.urlencode({
            "action": "query", "titles": "|".join(batch), "redirects": 1, "prop": "pageprops",
            "ppprop": "wikibase_item|disambiguation", "format": "json", "formatversion": 2,
        })
        data = (_get(f"https://en.wikipedia.org/w/api.php?{q}") or {}).get("query", {})
        land = {t: t for t in batch}
        fragment: dict[str, str] = {}
        redirected: set[str] = set()
        for hop in data.get("normalized", []):
            for t, now in list(land.items()):
                if now == hop["from"]:
                    land[t] = hop["to"]
        for hop in data.get("redirects", []):
            for t, now in list(land.items()):
                if now == hop["from"]:
                    land[t] = hop["to"]
                    redirected.add(t)
                    if hop.get("tofragment"):
                        fragment[t] = hop["tofragment"]
        pages = {p["title"]: p for p in data.get("pages", [])}
        for t in batch:
            p = pages.get(land[t])
            props = (p or {}).get("pageprops", {})
            ok = p and not p.get("missing") and "disambiguation" not in props and props.get("wikibase_item")
            cache[t] = {"title": p["title"], "qid": props["wikibase_item"], "redirect": t in redirected,
                        "fragment": fragment.get(t)} if ok else None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False))
        time.sleep(0.05)
    return {x: cache.get(x) for x in labels}


def sitelinks(qids: list[str], refresh: bool) -> dict[str, int]:
    path = CACHE / "physics" / "sitelinks.json"
    cache = {} if refresh or not path.exists() else json.loads(path.read_text())
    todo = [q for q in dict.fromkeys(qids) if q not in cache]
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(batch),
                                    "props": "sitelinks", "format": "json"})
        ents = (_get(f"https://www.wikidata.org/w/api.php?{q}") or {}).get("entities", {})
        for qid in batch:
            cache[qid] = len((ents.get(qid) or {}).get("sitelinks", {}))
        path.write_text(json.dumps(cache))
        time.sleep(0.05)
    return {q: cache.get(q, 0) for q in qids}


# --- the tree ---------------------------------------------------------------

def broadens(label: str, title: str) -> bool:
    """Whether a title says less than the label: "Vacuum technology" landing
    on *Vacuum*, "Plasma sources" on *Plasma (physics)*."""
    words = _fold(re.sub(r"\s*\(.*?\)", "", title))
    have = [_forms(w) for w in _fold(label)]
    return len(words) < len(have) and all(any(_forms(w) & h for h in have) for w in words)


def lookups(label: str) -> list[str]:
    """What to look a label up as: a hand-given title, else the label."""
    return [TITLES.get(label, label)]


def accept_pages(labels: list[str], pages: dict[str, dict | None], links: dict[str, int]) -> dict[str, dict]:
    """The page each label is believed to name.

    Named for it, give or take a plural, it is believed outright. A redirect
    is believed too, being Wikipedia's own statement that two names mean one
    thing ("Gravitation" to *Gravity*, "Extrasolar planets" to *Exoplanet*),
    unless it lands in a section ("Classical optics" to *Optics*, the article
    above it), or on a broader title. `TITLES` gives the rest. And a page
    belongs to one concept: one named for it outright wins, and a page several
    concepts reach only otherwise is nobody's ("Atomic spectra" and "Laser
    spectroscopy" both redirect to *Spectroscopy*).
    """
    exact, other = {}, {}
    for lab in labels:
        if lab in NOT_THE_SAME:
            continue
        options = []
        for i, text in enumerate(lookups(lab)):
            p = pages.get(text)
            if not p:
                continue
            if named_for(text, p["title"]) or lab in TITLES:
                options.append((i == 0 and lab not in TITLES, p))
            elif p.get("redirect") and not p.get("fragment") and not broadens(text, p["title"]):
                options.append((False, p))
        if not options:
            continue
        # The label's own page first, then the most famous part.
        whole, p = max(options, key=lambda o: (o[0], links.get(o[1]["qid"], 0)))
        (exact if whole else other)[lab] = p
    taken = {p["qid"] for p in exact.values()}
    by_page: dict[str, list[str]] = defaultdict(list)
    for lab, p in other.items():
        by_page[p["qid"]].append(lab)
    for lab, p in other.items():
        if p["qid"] not in taken and len(by_page[p["qid"]]) == 1:
            exact[lab] = p
    return exact


def build(concepts: dict[str, dict], disciplines: dict[str, dict], parent: dict[str, str],
          pages: dict[str, dict | None], links: dict[str, int], min_sitelinks: int) -> tuple[dict, dict]:
    believed = accept_pages([concepts[c]["label"] for c in parent], pages, links)

    def page(c: str) -> dict | None:
        return believed.get(concepts[c]["label"])

    famous = {c for c in parent if page(c) and links.get(page(c)["qid"], 0) >= min_sitelinks}

    def depth_of(c: str) -> int:
        n = 0
        while c in concepts:
            c, n = parent[c], n + 1
        return n

    keep = set()
    for c in famous:
        while c in concepts and c not in keep:
            keep.add(c)
            c = parent[c]
    kids: dict[str, list[str]] = defaultdict(list)
    for c in keep:
        kids[parent[c]].append(c)

    # A famous concept with one thing beneath it would be spliced out as a
    # pass-through, and the famous thing lost: Astronomical black holes, the
    # black hole itself, vanished above Primordial black holes. It is kept as
    # the leaf instead, and what was under it goes.
    def cut(c: str) -> None:
        for k in kids.pop(c, []):
            keep.discard(k)
            cut(k)

    for c in sorted(keep, key=lambda c: depth_of(c)):
        if c in keep and c in famous and len(kids.get(c, [])) == 1:
            cut(c)

    # Names are labels, which a reader can use; a label PhySH gives two
    # concepts is told apart by its parent's.
    count = defaultdict(int)
    for c in keep:
        count[concepts[c]["label"].lower()] += 1

    def name_of(c: str) -> str:
        lab = concepts[c]["label"]
        if count[lab.lower()] == 1:
            return lab
        up = parent[c]
        return f"{lab} ({concepts[up]['label'] if up in concepts else disciplines[up]['label']})"

    def make(c: str) -> dict:
        children = sorted((make(k) for k in kids[c]), key=lambda n: (bool(n.get("children")), n["name"].lower()))
        p = page(c)
        aliases = [a for a in concepts[c]["aliases"] if a.lower() != concepts[c]["label"].lower()]
        if p and p["title"].lower() != concepts[c]["label"].lower():
            aliases.insert(0, p["title"])
        name = name_of(c)
        return node(name, label=concepts[c]["label"] if name != concepts[c]["label"] else None,
                    aliases=list(dict.fromkeys(aliases))[:6] or None, children=children or None)

    tops = []
    for d in sorted(disciplines, key=lambda d: disciplines[d]["label"]):
        if kids[d]:
            children = sorted((make(k) for k in kids[d]), key=lambda n: (bool(n.get("children")), n["name"].lower()))
            tops.append(node(disciplines[d]["label"], rank="Discipline", children=children))
    tree = collapse_lone_children(node("Physics", children=tops),
                                  keep={disciplines[d]["label"] for d in disciplines})

    titles = {name_of(c): page(c)["title"] for c in keep if page(c)}
    titles.update(DISCIPLINE_ARTICLES)
    return tree, titles


def info_for(tree: dict, titles: dict[str, str]) -> dict[str, dict]:
    found = summaries(sorted(set(titles.values()) | {"Physics"}))
    names = set()

    def walk(n: dict) -> None:
        names.add(n["name"])
        for c in n.get("children") or []:
            walk(c)

    walk(tree)
    titles = {**titles, "Physics": "Physics"}
    out = {}
    for name in names:
        entry = info_entry(found.get(titles.get(name, "")))
        if entry:
            out[name] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-sitelinks", type=int, default=MIN_SITELINKS)
    ap.add_argument("--refresh", action="store_true", help="download PhySH and look titles up again")
    args = ap.parse_args()

    concepts, disciplines = read_scheme(load(args.refresh))
    parent = choose_parents(concepts, disciplines)
    pages = resolve_titles([t for c in parent for t in lookups(concepts[c]["label"])], args.refresh)
    links = sitelinks(sorted({p["qid"] for p in pages.values() if p}), args.refresh)
    tree, titles = build(concepts, disciplines, parent, pages, links, args.min_sitelinks)
    info = info_for(tree, titles)
    write_dataset("physics", tree, info)


if __name__ == "__main__":
    main()
