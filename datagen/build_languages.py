#!/usr/bin/env python3
"""datasets/languages — the world's best-known languages, on Glottolog's
family tree.

Glottolog (https://glottolog.org, CC BY 4.0) classifies every language it
knows into families and subgroups: 8,600 languages, 4,800 families and
subgroups. That is the tree. Which languages are *leaves* is decided by fame,
as TaxoQuiz decided which species: the number of Wikipedias with an article
on the language (Wikidata sitelinks, joined on the Glottocode, property P1394).
`MIN_SITELINKS` sets the bar; at 40 it is about 400 languages, from English to
Yoruba to Basque.

Decisions, each a way to get this quietly wrong:

- **No ladder.** A "family" can be Japonic (two branches) or Indo-European
  (fourteen levels deep), so no constant could say how specific "sharing a
  family" is. The manifest has no ladder, and every node is placed by the shape
  below it — the fraction of the way down its longest lineage. This dataset is
  the test that the engine works with nothing but a tree.
- **Glottolog's pseudo-families are left out**: Sign Language, Pidgin,
  Artificial Language (Esperanto), Mixed Language, Speech Register,
  Unclassifiable, Unattested, Bookkeeping. They are filing categories, not
  lineages, and sharing one would score as kinship.
- **Single-child subgroups are spliced out**, except the families themselves.
  A pass-through is never anyone's LCA; Glottolog's Spanish sits 13 subgroups
  down Indo-European, and most of those are chains once the tree is cut to 400
  languages. A family is kept even with one member, since "Japonic" says
  something a reader wants to know.
- **Labels are Wikidata's English names** ("German"), Glottolog's own
  ("Standard German") kept as an alias. Collisions are qualified with
  Glottolog's name, which is what tells them apart.
- **What most people call a language is not always a Glottolog language.**
  Glottolog splits finely, and Wikidata hangs the famous name on whatever level
  it means: "Arabic" on the *subgroup* of 37 Arabics, "Croatian" and
  "Cantonese" on *dialects*. Taken at face value, Persian, Arabic, Hebrew and
  Swahili were simply missing. Two rules put them back:
  - a famous **dialect** lends its name to its language — as an alias where the
    language is already chosen (typing "Cantonese" finds Yue Chinese), and as
    the label where it was not (Bahasa Indonesia makes Standard Indonesian
    "Indonesian"). Derived, no list.
  - a famous **subgroup** names its standard variety, from `STANDARD_VARIETY`.
    This one is a list, because no rule picks Standard Arabic out of 37 Arabics:
    by Wikidata's own counts it is the *least* linked of them, the fame having
    gone to the subgroup. Each entry is checked to be a language inside its
    subgroup, and subgroups with no one standard (Kurdish, Pashto, Quechua,
    Aramaic) are left out rather than guessed at.

Usage:
    python3 datagen/build_languages.py [--min-sitelinks 40] [--refresh]
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.parse
import urllib.request
import zipfile

from common import CACHE, USER_AGENT, collapse_lone_children, fetch, node, write_dataset
from wikipedia import info_entry, summaries, title_from_url

LANGUOIDS = "https://cdstar.eva.mpg.de//bitstreams/EAEA0-608B-9919-A962-0/glottolog_languoid.csv.zip"
MIN_SITELINKS = 40
PSEUDO_FAMILIES = {
    "book1242",  # Bookkeeping
    "sign1238",  # Sign Language
    "uncl1493",  # Unclassifiable
    "pidg1258",  # Pidgin
    "unat1236",  # Unattested
    "arti1236",  # Artificial Language
    "spee1234",  # Speech Register
    "mixe1287",  # Mixed Language
}
# A famous subgroup and the language its English name means. See the docstring.
STANDARD_VARIETY = {
    "arab1395": "stan1318",  # Arabic -> Standard Arabic
    "fars1254": "west2369",  # Persian -> Western Farsi (Iranian Persian)
    "gree1276": "mode1248",  # Greek -> Modern Greek
    "hebr1246": "hebr1245",  # Hebrew -> Modern Hebrew
    "swah1254": "swah1253",  # Swahili -> Swahili (Kiswahili)
    "arme1241": "nucl1235",  # Armenian -> Eastern Armenian
    "taga1269": "taga1270",  # Tagalog
    "azer1255": "nort2697",  # Azerbaijani -> North Azerbaijani
    "alba1267": "tosk1239",  # Albanian -> Tosk, the standard's base
    "uzbe1247": "nort2690",  # Uzbek -> Northern Uzbek
    "mong1331": "halh1238",  # Mongolian -> Halh Mongolian
    "khme1253": "cent1989",  # Khmer -> Central Khmer
    "glob1245": "java1254",  # Javanese
    "mala1537": "plat1254",  # Malagasy -> Plateau Malagasy (Merina), the standard's base
}

SPARQL = """SELECT ?g ?item ?sl ?label ?enwiki WHERE {
  ?item wdt:P1394 ?g ; wikibase:sitelinks ?sl .
  OPTIONAL { ?item rdfs:label ?label FILTER(lang(?label) = "en") }
  OPTIONAL { ?enwiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
}"""


def read_languoids(path) -> dict[str, dict]:
    with zipfile.ZipFile(path) as z, z.open("languoid.csv") as f:
        return {r["id"]: r for r in csv.DictReader(io.TextIOWrapper(f, "utf-8"))}


def wikidata(refresh: bool) -> dict[str, dict]:
    """Glottocode to the best-linked Wikidata item that carries it."""
    path = CACHE / "glottolog" / "wikidata.json"
    if refresh or not path.exists():
        url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": SPARQL})
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=300) as resp:
            path.write_bytes(resp.read())
    best: dict[str, dict] = {}
    for b in json.loads(path.read_text())["results"]["bindings"]:
        g, sl = b["g"]["value"], int(b["sl"]["value"])
        # Several items can carry one Glottocode (a language and its standard
        # form, say). The best-linked is the one people mean.
        if g not in best or sl > best[g]["sitelinks"]:
            best[g] = {
                "sitelinks": sl,
                "label": b.get("label", {}).get("value", ""),
                "enwiki": b.get("enwiki", {}).get("value", ""),
            }
    return best


def build(languoids: dict[str, dict], wd: dict[str, dict], min_sitelinks: int) -> tuple[dict, dict]:
    def family_of(r: dict) -> str:
        return r["family_id"] or r["id"]

    def famous(gid: str) -> bool:
        return wd.get(gid, {}).get("sitelinks", 0) >= min_sitelinks

    def playable(r: dict) -> bool:
        return r["bookkeeping"] != "True" and family_of(r) not in PSEUDO_FAMILIES

    chosen_ids = {g for g, r in languoids.items() if r["level"] == "language" and playable(r) and famous(g)}
    # A language's English name where Wikidata filed it elsewhere, and the
    # other names it goes by.
    named: dict[str, str] = {}
    aliases: dict[str, list[str]] = {}

    for sub, std in STANDARD_VARIETY.items():
        s, r = languoids.get(sub), languoids.get(std)
        if not s or not r or r["level"] != "language" or not _under(std, sub, languoids):
            raise SystemExit(f"STANDARD_VARIETY {sub} -> {std} is no longer a language inside that subgroup")
        if famous(sub) and playable(r):
            chosen_ids.add(std)
            named[std] = wd[sub]["label"]

    for g, r in languoids.items():
        if r["level"] != "dialect" or not famous(g) or not playable(r):
            continue
        lang = g
        while languoids[lang]["level"] != "language":
            lang = languoids[lang]["parent_id"]
        dialect_name = wd[g]["label"]
        if lang in chosen_ids:
            aliases.setdefault(lang, []).append(dialect_name)
        else:
            chosen_ids.add(lang)
            named[lang] = dialect_name

    chosen = [languoids[g] for g in chosen_ids]

    # Labels: Wikidata's English name, unless two chosen languages share it.
    def label_for(r: dict) -> str:
        return named.get(r["id"]) or wd.get(r["id"], {}).get("label") or r["name"]

    seen: dict[str, int] = {}
    for r in chosen:
        seen[label_for(r).lower()] = seen.get(label_for(r).lower(), 0) + 1

    # Every chosen language's lineage, top-level family first.
    children: dict[str, list[str]] = {}
    tops: list[str] = []
    for r in sorted(chosen, key=lambda r: r["name"]):
        chain = [r["id"]]
        while languoids[chain[-1]]["parent_id"]:
            chain.append(languoids[chain[-1]]["parent_id"])
        chain.reverse()
        if chain[0] not in tops:
            tops.append(chain[0])
        for parent, child in zip(chain, chain[1:]):
            kids = children.setdefault(parent, [])
            if child not in kids:
                kids.append(child)

    info: dict[str, dict] = {}
    titles: dict[str, str] = {}

    def make(gid: str, is_top: bool) -> dict:
        r = languoids[gid]
        link = wd.get(gid, {}).get("enwiki")
        if link:
            titles[gid] = title_from_url(link)
        kids = [make(c, False) for c in sorted(children.get(gid, []), key=lambda c: languoids[c]["name"])]
        if not kids:
            label = label_for(r)
            if seen[label.lower()] > 1:
                label = f"{label} ({r['name']})"
            names = [wd.get(gid, {}).get("label", ""), r["name"], *aliases.get(gid, []), gid]
            others = [a for a in dict.fromkeys(names) if a and a.lower() != label.lower()]
            return node(gid, "Language", label=label, aliases=others)
        rank = "Family" if is_top else None
        # The English name too, so explore's search finds Sinitic as "Chinese".
        english = wd.get(gid, {}).get("label", "")
        group_aliases = [english] if english and english.lower() != r["name"].lower() else None
        return node(gid, rank, label=r["name"], children=kids, aliases=group_aliases)

    tree = node("languages", label="Languages", children=[
        make(t, True) for t in sorted(tops, key=lambda t: (-_leaf_count(t, children), languoids[t]["name"]))
    ])
    tree = collapse_lone_children(tree, keep=set(tops))

    kept = set()

    def walk(n: dict) -> None:
        kept.add(n["name"])
        for c in n.get("children") or []:
            walk(c)

    walk(tree)
    wanted = {gid: t for gid, t in titles.items() if gid in kept}
    got = summaries(sorted(set(wanted.values())))
    for gid, title in wanted.items():
        entry = info_entry(got.get(title))
        if entry:
            info[gid] = entry
    return tree, info


def _under(gid: str, ancestor: str, languoids: dict[str, dict]) -> bool:
    while gid:
        if gid == ancestor:
            return True
        gid = languoids[gid]["parent_id"]
    return False


def _leaf_count(gid: str, children: dict[str, list[str]]) -> int:
    kids = children.get(gid, [])
    return 1 if not kids else sum(_leaf_count(c, children) for c in kids)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-sitelinks", type=int, default=MIN_SITELINKS)
    ap.add_argument("--refresh", action="store_true", help="download Glottolog and query Wikidata again")
    args = ap.parse_args()
    languoids = read_languoids(fetch(LANGUOIDS, CACHE / "glottolog" / "glottolog_languoid.csv.zip", refresh=args.refresh))
    tree, info = build(languoids, wikidata(args.refresh), args.min_sitelinks)
    write_dataset("languages", tree, info)


if __name__ == "__main__":
    main()
