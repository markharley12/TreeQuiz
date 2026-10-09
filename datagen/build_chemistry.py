"""Build `datasets/chemistry`: famous chemicals, on ChEBI's classes.

ChEBI, Chemical Entities of Biological Interest (https://www.ebi.ac.uk/chebi,
CC BY 4.0), files about 219,000 entities under classes by structure: caffeine
is a trimethylxanthine, a methylxanthine, a xanthine, a purine…; iron is an
iron group element atom, a transition element atom, a metal atom. That is the
tree, and the leaves are the chemicals people have heard of.

**Which chemicals.** Wikidata items with a ChEBI ID (P683) and at least
`MIN_SITELINKS` Wikipedias, which are either a chemical element or have an
InChIKey (P235). The InChIKey is what separates a compound from a class:
"alkaloid", "steroid" and "vitamin" all have ChEBI IDs and plenty of
Wikipedias, and no structure. It also loses a few famous names that Wikidata
files as classes — glucose (as against D-glucose), penicillin, chlorophyll —
which is the price of a rule over a list.

**It is a lattice, not a tree.** ChEBI gives caffeine two parents, ethanol
four, rifampicin six, and they are not all of one kind: ethanol is a primary
alcohol and also a "volatile organic compound", a class by behaviour, which
sits four levels from the root where primary alcohol sits nine. Each node
takes the parent with the **longest path to the root**, TaxoQuiz's rule for
Wikidata's several parents and PhySH's: the most specific class, and in
practice the structural one. Ties go to the parent with more children in
ChEBI, the more central class.

**Shape.** A famous chemical with one famous chemical beneath it is the leaf
and the one beneath goes, so that glucose is not spliced out above D-glucose.
Chains of one class are spliced out. There is no ladder: depth is all a
class has to say, and the tree's shape places it.

**Names.** A leaf is labelled by its English Wikipedia title, the name people
use ("Aspirin", not acetylsalicylic acid), less any "(element)"; it is named
by its ChEBI name, which the app shows beneath. Classes are ChEBI's names.
Popups are Wikipedia's, for leaves by their title and for classes where an
article is named for the class.
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
from wikipedia import _get, info_entry, named_for, summaries

RELEASE = 255
SOURCE = f"https://ftp.ebi.ac.uk/pub/databases/chebi/archive/rel{RELEASE}/ontology/chebi_lite.obo.gz"
ROOT = "CHEBI:24431"   # chemical entity
ATOM = "CHEBI:33250"
MIN_SITELINKS = 45
ELEMENT = "Q11344"
# Classes by what a chemical does or what state it is in, which ChEBI files
# under is_a beside the structural ones. Passed over where a structural parent
# exists: the noble gases went under "gas molecular entity", away from every
# other atom, and penicillins under "penicillin allergen".
NOT_STRUCTURE = re.compile(r"\b(allergen|drug|agent|antibiotic)\b|^gas molecular entity$|^volatile organic compound$")

# Wikidata items whose ChEBI ID is wrong, and the right one. Leads for fixing
# Wikidata: copper(II) oxide carries "CU-O LINKAGE", a bond, not the compound.
CHEBI_FIXES = {"Q421787": "CHEBI:75955"}

SPARQL = """SELECT ?item ?chebi ?sl WHERE {
  ?item wdt:P683 ?chebi ; wikibase:sitelinks ?sl .
  FILTER(?sl >= %d)
}"""


def load_chebi(refresh: bool) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Term id to name, and to its is_a parents; obsolete terms left out."""
    path = fetch(SOURCE, CACHE / "chemistry" / f"chebi_lite-{RELEASE}.obo.gz", refresh=refresh)
    names: dict[str, str] = {}
    parents: dict[str, list[str]] = defaultdict(list)
    cur: dict | None = None
    terms = []
    for line in gzip.open(path, "rt"):
        line = line.rstrip("\n")
        if line.startswith("["):
            cur = {"is_a": []} if line == "[Term]" else None
            if cur is not None:
                terms.append(cur)
            continue
        if cur is None or ": " not in line:
            continue
        key, value = line.split(": ", 1)
        if key in ("id", "name"):
            cur[key] = value
        elif key == "is_a":
            cur["is_a"].append(value.split(" !")[0].split()[0])
        elif key == "is_obsolete":
            cur["obsolete"] = True
    for t in terms:
        if "id" in t and not t.get("obsolete"):
            names[t["id"]] = t.get("name", t["id"])
            parents[t["id"]] = t["is_a"]
    return names, parents


def wikidata(min_sitelinks: int, refresh: bool) -> dict[str, dict]:
    """Item to {sitelinks, chebi ids, element?, inchikey?, title, label}."""
    path = CACHE / "chemistry" / f"wikidata-{min_sitelinks}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    q = urllib.parse.urlencode({"query": SPARQL % min_sitelinks, "format": "json"})
    rows = _get(f"https://query.wikidata.org/sparql?{q}")["results"]["bindings"]
    items: dict[str, dict] = {}
    for r in rows:
        qid = r["item"]["value"].rsplit("/", 1)[1]
        it = items.setdefault(qid, {"sitelinks": int(r["sl"]["value"]), "chebi": []})
        it["chebi"].append("CHEBI:" + r["chebi"]["value"])
    ids = sorted(items)
    for i in range(0, len(ids), 50):
        batch = ids[i:i + 50]
        q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(batch), "props": "claims|sitelinks|labels",
                                    "languages": "en", "sitefilter": "enwiki", "format": "json"})
        ents = _get(f"https://www.wikidata.org/w/api.php?{q}")["entities"]
        for qid in batch:
            e = ents.get(qid, {})
            claims = e.get("claims", {})
            instance = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in claims.get("P31", [])]
            items[qid].update({
                "inchikey": "P235" in claims,
                "element": ELEMENT in instance,
                "title": e.get("sitelinks", {}).get("enwiki", {}).get("title"),
                "label": e.get("labels", {}).get("en", {}).get("value"),
            })
        time.sleep(0.05)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False))
    return items


def depths(parents: dict[str, list[str]]) -> dict[str, int]:
    """Longest path from each term up to the root, by is_a."""
    out: dict[str, int] = {}

    def longest(t: str) -> int:
        if t in out:
            return out[t]
        out[t] = 0   # guards a cycle, should ChEBI ever have one
        out[t] = max((longest(p) + 1 for p in parents.get(t, []) if p in parents), default=0)
        return out[t]

    for t in list(parents):
        longest(t)
    return out


def under(t: str, ancestor: str, parents: dict[str, list[str]], seen: set | None = None) -> bool:
    if t == ancestor:
        return True
    seen = seen if seen is not None else set()
    seen.add(t)
    return any(under(p, ancestor, parents, seen) for p in parents.get(t, []) if p not in seen)


def choose(items: dict[str, dict], names: dict[str, str], parents: dict[str, list[str]],
           depth: dict[str, int]) -> dict[str, dict]:
    """ChEBI term to the item it stands for, for the chemicals in play. An
    item with several ChEBI IDs takes the deepest, the most specific; a term
    several items share goes to the most famous."""
    out: dict[str, dict] = {}
    by_name = {n: t for t, n in names.items()}
    for qid, it in sorted(items.items(), key=lambda kv: -kv[1]["sitelinks"]):
        if not it.get("title") or not (it.get("inchikey") or it.get("element")):
            continue
        terms = [t for t in ([CHEBI_FIXES[qid]] if qid in CHEBI_FIXES else it["chebi"]) if t in names]
        # An element is its atom: Wikidata gives iron "iron atom" and also
        # "iron(0)" and others, and the deepest of those is not an atom at
        # all, which put iron among its oxides and away from cobalt.
        if it.get("element"):
            terms = [t for t in terms if under(t, ATOM, parents)]
            # Some elements carry no atom ID on Wikidata at all (carbon,
            # sulfur, helium…); ChEBI names its atoms "<element> atom".
            if not terms and it.get("label") and by_name.get(f"{it['label'].lower()} atom"):
                terms = [by_name[f"{it['label'].lower()} atom"]]
        if not terms:
            continue
        term = max(terms, key=lambda t: (depth.get(t, 0), t))
        if term not in out:
            out[term] = {**it, "qid": qid}
    return out


def label_of(title: str) -> str:
    """'Mercury (element)' -> 'Mercury'."""
    return re.sub(r"\s+\([^)]*\)$", "", title)


def build(chosen: dict[str, dict], names: dict[str, str], parents: dict[str, list[str]],
          depth: dict[str, int]) -> tuple[dict, dict[str, str]]:
    children_count: dict[str, int] = defaultdict(int)
    for ps in parents.values():
        for p in ps:
            children_count[p] += 1

    def parent_of(t: str) -> str | None:
        ps = [p for p in parents.get(t, []) if p in names]
        ps = [p for p in ps if not NOT_STRUCTURE.search(names[p])] or ps
        return max(ps, key=lambda p: (depth.get(p, 0), children_count[p], p)) if ps else None

    up: dict[str, str] = {}
    for t in chosen:
        while t != ROOT and t not in up:
            p = parent_of(t)
            if p is None:
                break
            up[t] = p
            t = p
    kids: dict[str, list[str]] = defaultdict(list)
    for t, p in up.items():
        kids[p].append(t)

    def cut(t: str) -> None:
        for k in kids.pop(t, []):
            if k in chosen:
                del chosen[k]
            cut(k)

    order = sorted(up, key=lambda t: depth.get(t, 0))
    for t in order:
        if t in chosen and len(kids.get(t, [])) == 1:
            cut(t)

    def alive(t: str) -> bool:
        return t in chosen or any(alive(k) for k in kids.get(t, []))

    def make(t: str) -> dict:
        live = [make(k) for k in kids.get(t, []) if alive(k)]
        live.sort(key=lambda n: (bool(n.get("children")), n.get("label", n["name"]).lower()))
        if t in chosen and not live:
            it = chosen[t]
            label = label_of(it["title"])
            aliases = [a for a in (it.get("label"), names[t]) if a and a.lower() != label.lower()]
            return node(names[t], label=label, aliases=list(dict.fromkeys(aliases)) or None)
        return node(names[t], children=live)

    tree = collapse_lone_children(make(ROOT))
    titles = {names[t]: it["title"] for t, it in chosen.items()}
    return tree, titles


def info_for(tree: dict, titles: dict[str, str]) -> dict[str, dict]:
    """Leaves by their own article; classes by an article named for them."""
    groups: list[str] = []

    def walk(n: dict) -> None:
        if n.get("children"):
            groups.append(n["name"])
            for c in n["children"]:
                walk(c)

    walk(tree)
    # ChEBI names its element classes "noble gas atom", "alkali metal atom";
    # the article is "Noble gas".
    guesses = {g: (g[:-5] if g.endswith(" atom") else g) for g in groups}
    guesses = {g: t[0].upper() + t[1:] for g, t in guesses.items()}
    found = summaries(sorted(set(titles.values()) | set(guesses.values())))
    out = {}
    for name, title in titles.items():
        entry = info_entry(found.get(title))
        if entry:
            out[name] = entry
    for g, title in guesses.items():
        s = found.get(title)
        if s and named_for(title, s["title"]):
            entry = info_entry(s)
            if entry:
                out[g] = entry
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-sitelinks", type=int, default=MIN_SITELINKS)
    ap.add_argument("--refresh", action="store_true", help="download ChEBI and query Wikidata again")
    args = ap.parse_args()

    names, parents = load_chebi(args.refresh)
    depth = depths(parents)
    chosen = choose(wikidata(args.min_sitelinks, args.refresh), names, parents, depth)
    tree, titles = build(chosen, names, parents, depth)
    write_dataset("chemistry", tree, info_for(tree, titles))


if __name__ == "__main__":
    main()
