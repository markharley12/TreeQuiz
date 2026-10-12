#!/usr/bin/env python3
"""datasets/cities — the world's best-known cities, by where they are.

World → continent → subregion → country → first-level region (a state,
province, Land, prefecture…) → city. So Lyon and Paris meet at France, Paris
and Berlin at Western Europe, Paris and Rome at Europe.

Sources:

- **Continents and subregions**: Natural Earth's countries (public domain,
  pinned at `NATURAL_EARTH`), whose `CONTINENT` is the seven-continent model
  and whose `SUBREGION` follows the UN's geoscheme ("Western Europe",
  "Eastern Africa"). Joined to Wikidata by the QID Natural Earth carries,
  else by ISO 3166-1 numeric code. The UN's own M49 page is not used: its
  terms forbid redistribution and derivative works.
- **Cities, their countries and regions**: Wikidata (CC0). A city is an
  instance of *city* (Q515) or a subclass, or a place of at least
  `POP_FLOOR` people that is an instance of a settlement or municipality
  (`SETTLED`), chosen by how many Wikipedias cover it (`MIN_SITELINKS`), as
  TaxoQuiz chose species. Its country is P17; its region is the nearest
  *first-level administrative country subdivision* (Q10864048) up its P131
  chain.
- **Popup text**: English Wikipedia.

Decisions:

- **Not only what Wikidata calls a city.** Madrid is only a *municipality of
  Spain* there, Marseille a *commune of France*, Tabriz a *city of Iran* —
  none a subclass of *city* — and *city* alone lost 34 cities at
  `MIN_SITELINKS`, Madrid the most famous. Any populous settlement or
  municipality is taken, which needs the population floor: a municipality can
  be a hamlet. Tiny capitals (Valletta, Vaduz) are typed as cities and come
  in that way.
- **A small place must be a capital.** Below `SMALL_TOWN` people a city is
  kept only as the capital of something (Wikidata's P1376: Valletta,
  Vaduz, Pierre, South Dakota) or as a city-state. Sitelinks can be made in
  bulk: Monte Águila, a Chilean town of 6,500, had 206 of them, more than
  Seville, and Łobez and Uetersen were the same.
- **A place inside another chosen city is part of it**, not a city:
  Manhattan and Brooklyn (in New York City) and Hollywood (in Los Angeles)
  are settlements on Wikidata, and are dropped.
- **Russia is in Europe, Novosibirsk with it.** Natural Earth places a
  country whole, and a city cannot leave its country. Turkey is Asia, Egypt
  Africa, for the same reason. South America has no subregion but itself, so
  its countries sit straight under the continent.
- **Island states in the open ocean** (Natural Earth's "Seven seas"), such as
  the Maldives and Mauritius, take the UN continent Natural Earth also gives.
- **Historical countries are dropped**: Debrecen's P17 lists nine, from the
  Kingdom of Hungary on; only countries on today's map count.
- **A city in two countries** (Jerusalem: Israel and Palestine; Sevastopol:
  Russia and Ukraine) is filed under the subregion they share, under neither
  country and in no region.
- **A city that is its own region sits straight under its country.** Berlin
  is a German state, Tokyo a prefecture, Moscow a federal subject; filing
  Berlin under "Berlin" says nothing. Where a city is both its own region and
  inside another, the other wins (Istanbul is a metropolitan municipality, and
  in Istanbul Province).
- **Several regions: the country's usual kind, then the nearest.** Candidates
  are narrowed to the type most of the country's cities have (a Turkish city
  goes to its province, not an Ottoman sanjak), then to the fewest P131 steps
  away. A city still in two regions (Gothenburg) sits under its country.
  `NOT_REGION` names three first-level types that are not what a reader means
  by a region, such as Belgium's language communities.
- **A city-state is a leaf where its country would be**: Singapore, Monaco,
  Vatican City are each their own country on Wikidata.
- **A dissolved city is kept**: Vietnam abolished its provincial cities as
  administrative units in 2025, and Nha Trang is still a city. Ancient cities
  have no population and fall out on that, bar `EXCLUDE`.
- **A region holding one city is spliced out**, as every builder does with
  pass-throughs; continents, subregions and countries are kept, being the
  levels the game is about.
- **Labels drop a disambiguation the tree already gives**: "Portland, Oregon"
  is "Portland" under Oregon, unless another city would then share its label
  ("Birmingham" and "Birmingham, Alabama" stay as titled).

Usage:
    python3 datagen/build_cities.py [--min-sitelinks 120] [--refresh]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from common import CACHE, USER_AGENT, collapse_lone_children, fetch, node, write_dataset
from wikipedia import info_entry, summaries

MIN_SITELINKS = 120
FETCH_FLOOR = 60      # cities are fetched down to here, so tuning needs no refetch
NATURAL_EARTH = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/"
                 "geojson/ne_50m_admin_0_countries.geojson")
OPEN_OCEAN = "Seven seas (open ocean)"
# Natural Earth's region names, where Wikipedia's article on the region has another.
ARTICLES = {
    "Eastern Africa": "East Africa", "Northern Africa": "North Africa", "Middle Africa": "Central Africa",
    "Western Africa": "West Africa", "Eastern Asia": "East Asia", "South-Eastern Asia": "Southeast Asia",
    "Southern Asia": "South Asia", "Western Asia": "West Asia", "Australia and New Zealand": "Australasia",
}
BATCH = 200

POP_FLOOR = 50000     # for places that are settlements but not typed as cities
SMALL_TOWN = 20000    # below which a city must be a capital
# Settlements and municipalities: human settlement, municipality, city or town.
SETTLED = ("Q486972", "Q15284", "Q7930989")
CITIES = """SELECT DISTINCT ?c WHERE {
  ?c wdt:P31/wdt:P279* wd:Q515 ; wikibase:sitelinks ?sl . FILTER(?sl >= %d)
}"""
# Not walked through the class tree here: from a numeric filter, it timed out.
POPULOUS = """SELECT DISTINCT ?c WHERE {
  ?c wdt:P1082 ?p . FILTER(?p >= %d) ?c wikibase:sitelinks ?sl . FILTER(?sl >= %d)
}"""
SETTLEMENTS = ("""SELECT DISTINCT ?c WHERE {
  VALUES ?c { %s }
  VALUES ?root { """ + " ".join(f"wd:{q}" for q in SETTLED) + """ }
  ?c wdt:P31/wdt:P279* ?root
}""")
ABOUT = """SELECT ?c ?sl ?label ?enwiki ?country ?pop ?gone ?capital WHERE {
  VALUES ?c { %s }
  ?c wikibase:sitelinks ?sl .
  OPTIONAL { ?c rdfs:label ?label FILTER(lang(?label) = "en") }
  OPTIONAL { ?enwiki schema:about ?c ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?c wdt:P17 ?country }
  OPTIONAL { ?c wdt:P1082 ?pop }
  BIND(EXISTS { ?c wdt:P576 ?d } AS ?gone)
  BIND(EXISTS { ?c wdt:P1376 ?of } AS ?capital)
}"""
FIRST_LEVEL = """SELECT DISTINCT ?type ?typel WHERE {
  ?type wdt:P279* wd:Q10864048 .
  OPTIONAL { ?type rdfs:label ?typel FILTER(lang(?typel) = "en") }
}"""
UPWARD = """SELECT ?x ?up ?type ?gone WHERE {
  VALUES ?x { %s }
  OPTIONAL { ?x wdt:P131 ?up }
  OPTIONAL { ?x wdt:P31 ?type }
  BIND(EXISTS { ?x wdt:P576 ?d } AS ?gone)
}"""
PLACES = """SELECT ?x ?label ?enwiki ?m49 ?iso WHERE {
  VALUES ?x { %s }
  OPTIONAL { ?x rdfs:label ?label FILTER(lang(?label) = "en") }
  OPTIONAL { ?enwiki schema:about ?x ; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?x wdt:P2082 ?m49 }
  OPTIONAL { ?x wdt:P299 ?iso }
}"""
ALIASES = """SELECT ?c ?alt WHERE {
  VALUES ?c { %s }
  ?c skos:altLabel ?alt FILTER(lang(?alt) = "en")
}"""


def _sparql(query: str, retries: int = 4) -> list[dict]:
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query})
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.load(resp)["results"]["bindings"]
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(5 * 2 ** attempt)
    raise AssertionError("unreachable")


def _qid(b: dict, key: str) -> str | None:
    v = b.get(key, {}).get("value")
    return v.rsplit("/", 1)[1] if v else None


def _title(b: dict) -> str | None:
    v = b.get("enwiki", {}).get("value")
    return urllib.parse.unquote(v.rsplit("/wiki/", 1)[1]).replace("_", " ") if v else None


def _batched(query: str, qids: list[str]) -> list[dict]:
    rows = []
    for i in range(0, len(qids), BATCH):
        rows += _sparql(query % " ".join(f"wd:{q}" for q in qids[i:i + BATCH]))
        time.sleep(1)
    return rows


def wikidata(refresh: bool) -> dict:
    """Everything the build reads from Wikidata, fetched once at FETCH_FLOOR."""
    path = CACHE / "cities" / f"wikidata-{FETCH_FLOOR}-{POP_FLOOR}-v3.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    typed = {_qid(b, "c") for b in _sparql(CITIES % FETCH_FLOOR)}
    populous = sorted({_qid(b, "c") for b in _sparql(POPULOUS % (POP_FLOOR, FETCH_FLOOR))} - typed)
    settled = {_qid(b, "c") for b in _batched(SETTLEMENTS, populous)}
    print(f"wikidata: {len(typed)} cities and {len(settled)} other settlements at {FETCH_FLOOR}+ sitelinks")
    cities: dict[str, dict] = {}
    for b in _batched(ABOUT, sorted(typed | settled)):
        c = cities.setdefault(_qid(b, "c"), {"sitelinks": int(b["sl"]["value"]), "countries": [],
                                              "label": b.get("label", {}).get("value"), "title": _title(b),
                                              "population": None, "gone": b["gone"]["value"] == "true",
                                              "capital": b["capital"]["value"] == "true"})
        k = _qid(b, "country")
        if k and k not in c["countries"]:
            c["countries"].append(k)
        p = b.get("pop", {}).get("value")
        if p:
            try:
                c["population"] = max(c["population"] or 0, round(float(p)))
            except ValueError:
                pass   # an unknown value, "somevalue"
    graph = located_in(sorted(cities))
    places_wanted = sorted({k for c in cities.values() for k in c["countries"]}
                           | {r for q in cities for r, _, _ in first_level(q, graph)})
    places: dict[str, dict] = {}
    for b in _batched(PLACES, places_wanted):
        p = places.setdefault(_qid(b, "x"), {"label": None, "title": None, "codes": []})
        p["label"] = p["label"] or b.get("label", {}).get("value")
        p["title"] = p["title"] or _title(b)
        for key in ("m49", "iso"):
            v = b.get(key, {}).get("value")
            if v and v not in p["codes"]:
                p["codes"].append(v)
    aliases: dict[str, list[str]] = collections.defaultdict(list)
    for b in _batched(ALIASES, sorted(cities)):
        aliases[_qid(b, "c")].append(b["alt"]["value"])
    data = {"cities": cities, "graph": graph, "places": places, "aliases": aliases}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False))
    return data


def located_in(cities: list[str]) -> dict:
    """The P131 graph above `cities`: each item's parents (`up`), its types
    (`kinds`), whether it is dissolved (`gone`), and which types are
    first-level subdivisions (`types`, with their labels).

    Walked a level at a time rather than with `wdt:P131*`, which with the
    type test timed out at Wikidata for 200 cities at once. The graph is kept
    raw; which region a city is filed in is the build's decision (`region_of`)."""
    types = {_qid(b, "type"): b.get("typel", {}).get("value", "") for b in _sparql(FIRST_LEVEL)}
    up: dict[str, list[str]] = {}
    kinds: dict[str, list[str]] = {}
    gone: set[str] = set()
    todo = set(cities)
    while todo:
        print(f"  located in: {len(todo)} items")
        for b in _batched(UPWARD, sorted(todo)):
            x = _qid(b, "x")
            up.setdefault(x, [])
            kinds.setdefault(x, [])
            for key, into in (("up", up), ("type", kinds)):
                v = _qid(b, key)
                if v and v not in into[x]:
                    into[x].append(v)
            if b["gone"]["value"] == "true":
                gone.add(x)
        todo = {u for ups in up.values() for u in ups} - set(up)
    return {"types": types, "up": up, "kinds": kinds, "gone": sorted(gone)}


def first_level(city: str, graph: dict) -> list[tuple[str, str, int]]:
    """Every (region, type, steps) up a city's P131 chain, the city itself
    included at 0 steps, where the type is a first-level subdivision's and
    the region is not dissolved. The walk goes on past a hit, since a city
    can be a first-level unit inside another (Istanbul, in Istanbul
    Province); a region reached by two routes counts at the shorter."""
    gone, types = set(graph["gone"]), graph["types"]
    found: dict[tuple[str, str], int] = {}
    seen, frontier, steps = {city}, [city], 0
    while frontier:
        nxt = []
        for x in frontier:
            if x not in gone:
                for t in graph["kinds"].get(x, ()):
                    if t in types:
                        found.setdefault((x, t), steps)
            for u in graph["up"].get(x, ()):
                if u not in seen:
                    seen.add(u)
                    nxt.append(u)
        frontier, steps = nxt, steps + 1
    return [(r, t, n) for (r, t), n in found.items()]


# --- continents and subregions ----------------------------------------------

def natural_earth(refresh: bool) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Country QID to its [continent, subregion] — the subregion left out
    where it is the continent (South America) — and ISO 3166-1 numeric code
    to the QID Natural Earth gives that country."""
    path = fetch(NATURAL_EARTH, CACHE / "cities" / NATURAL_EARTH.rsplit("/", 1)[1], refresh=refresh)
    regions: dict[str, list[str]] = {}
    by_iso: dict[str, str] = {}
    for f in json.loads(path.read_text())["features"]:
        p = f["properties"]
        continent = p["REGION_UN"] if p["CONTINENT"] == OPEN_OCEAN else p["CONTINENT"]
        if continent == "Americas":
            continue      # South Georgia: no continent to give, and no cities
        sub = p["SUBREGION"]
        regions[p["WIKIDATAID"]] = [continent] if sub in (continent, OPEN_OCEAN) else [continent, sub]
        if p["ISO_N3"] and p["ISO_N3"] != "-99":
            by_iso[p["ISO_N3"]] = p["WIKIDATAID"]
    return regions, by_iso


# --- choosing ---------------------------------------------------------------

EXCLUDE = {
    "Q5684": "Babylon: an ancient city, with the population of its site",
    "Q1363": "Tripura: an Indian state, filed on Wikidata as a city",
    "Q1209": "Bremen the state, a city-state on Wikidata; the city Bremen is its own item",
    "Q43332": "Pompeii: the ancient city, with no people; the modern town is Pompei",
}
# First-level on Wikidata, but not the level a reader means by a region.
NOT_REGION = {
    "community of Belgium",                  # language communities, not places
    "decentralized administration of Greece",  # groups of the 13 regions
    "district of Albania",                   # abolished in 2015 for the counties
}
TYPE_RANKS = {
    "U.S. state": "State",
    "federative unit of Brazil": "State",
    "federated state of Germany": "State",
    "federative entity of Mexico": "State",
    "districts of Israel": "District",
    "direct-administered municipality": "Municipality",
    "metropolitan prefecture": "Prefecture",
    "first-level administrative division": "Region",
}
LADDER_RANKS = {"continent", "subregion", "country"}


def type_rank(label: str) -> str:
    """'federal subject of Russia' -> 'Federal subject'."""
    if label in TYPE_RANKS:
        return TYPE_RANKS[label]
    base = re.sub(r"\s+(of|in)\s+.*$", "", label)
    return base[:1].upper() + base[1:]


def label_of(title: str) -> str:
    """'Georgia (country)' -> 'Georgia'."""
    return re.sub(r"\s+\([^()]*\)$", "", title)


def countries_of(city: dict, places: dict, regions: dict, by_iso: dict) -> list[tuple[str, list[str]]]:
    """(country, [continent, subregion]) for each of a city's countries on
    today's map, which drops the historical ones (Debrecen's Kingdom of
    Hungary). A country is matched by its QID, else by ISO code: Wikidata's
    State of Palestine is Natural Earth's Palestine."""
    out = []
    for k in city["countries"]:
        if k in regions:
            out.append((k, regions[k]))
            continue
        hits = [by_iso[c] for c in places.get(k, {}).get("codes", []) if c in by_iso]
        if hits:
            out.append((k, regions[hits[0]]))
    return out


def choose(data: dict, regions: dict, by_iso: dict, min_sitelinks: int) -> list[dict]:
    """The cities to play with, each with its [continent, subregion] chain,
    country and region. A city in two countries is filed under what they
    share, under neither country and in no region."""
    cities, places, graph = data["cities"], data["places"], data["graph"]
    types = graph["types"]
    missing = NOT_REGION - set(types.values())
    if missing:
        raise SystemExit(f"NOT_REGION names types Wikidata no longer has: {sorted(missing)}")

    def candidates(q: str) -> list[tuple[str, str, int]]:
        return [(r, t, n) for r, t, n in first_level(q, graph)
                if r != q and types[t] not in NOT_REGION]

    # The usual kind of region in each country, over every city fetched.
    usual: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for q, c in cities.items():
        ks = countries_of(c, places, regions, by_iso)
        if len(ks) == 1:
            usual[ks[0][0]].update({t for _, t, _ in candidates(q)})

    chosen, unplaced, small = [], [], []
    for q, c in cities.items():
        if c["sitelinks"] < min_sitelinks or c["population"] is None or not c["title"] or q in EXCLUDE:
            continue
        ks = countries_of(c, places, regions, by_iso)
        if not ks:
            unplaced.append(c["label"])
            continue
        it = {"qid": q, **c, "country": None, "region": None, "region_type": None, "city_state": False}
        if len({k for k, _ in ks}) > 1:
            it["chain"] = []
            for step in zip(*(chain for _, chain in ks)):
                if len(set(step)) > 1:
                    break
                it["chain"].append(step[0])
        else:
            country, it["chain"] = ks[0]
            it["city_state"] = country == q     # Singapore is its own country
            if c["population"] < SMALL_TOWN and not (c["capital"] or it["city_state"]):
                small.append(c["title"])
                continue
            if not it["city_state"]:
                it["country"] = country
                cands = candidates(q)
                if cands:
                    best = max(usual[country][t] for _, t, _ in cands)
                    cands = [x for x in cands if usual[country][x[1]] == best]
                    near = min(n for _, _, n in cands)
                    picked = {(r, t) for r, t, n in cands if n == near}
                    if len({r for r, _ in picked}) == 1:
                        it["region"], it["region_type"] = min(picked)
        chosen.append(it)
    if unplaced:
        raise SystemExit(f"cities with no country on Natural Earth's map: {sorted(unplaced)}")
    if small:
        print(f"small towns that are no capital, left out: {sorted(small)}")
    taken = {it["qid"] for it in chosen}
    return [it for it in chosen if not (above(it["qid"], graph) & taken)]


def above(q: str, graph: dict) -> set[str]:
    """Everything up a place's P131 chain, itself left out."""
    seen: set[str] = set()
    frontier = [q]
    while frontier:
        frontier = [u for x in frontier for u in graph["up"].get(x, ()) if u not in seen and u != q]
        seen.update(frontier)
    return seen


# --- building ---------------------------------------------------------------

def city_labels(chosen: list[dict], places: dict) -> None:
    """A city's label is its title less a qualifier its lineage already
    gives — "Portland, Oregon" under Oregon is "Portland" — unless that would
    give two cities one label."""
    def short(it: dict) -> str:
        title = label_of(it["title"])
        head, _, tail = title.partition(", ")
        context = {label_of(places.get(x, {}).get("title") or "") for x in (it["country"], it["region"]) if x}
        return head if tail and tail in context else title
    counts = collections.Counter(short(it).casefold() for it in chosen)
    for it in chosen:
        s = short(it)
        it["label"] = s if counts[s.casefold()] == 1 else it["title"]


def city_aliases(chosen: list[dict], aliases: dict, labels: dict[str, str]) -> None:
    """Wikidata's English alternative names ("Bombay", "NYC"), less any that
    is another city's label or is claimed by two cities."""
    taken = {it["label"].casefold() for it in chosen}
    owners: collections.Counter = collections.Counter()
    found: dict[str, list[str]] = {}
    for it in chosen:
        seen, out = {it["label"].casefold()}, []
        for a in [labels.get(it["qid"]) or "", it["title"], *sorted(aliases.get(it["qid"], []))]:
            a = a.strip()
            if not a or len(a) > 40 or "(" in a or not re.search(r"[A-Za-z]", a) or a.casefold() in seen:
                continue
            seen.add(a.casefold())
            out.append(a)
        found[it["qid"]] = out
        owners.update({a.casefold() for a in out})
    for it in chosen:
        it["aliases"] = [a for a in found[it["qid"]] if a.casefold() not in taken and owners[a.casefold()] == 1]


def build(data: dict, regions: dict, by_iso: dict, min_sitelinks: int) -> tuple[dict, dict[str, str]]:
    """The tree, and node name to Wikipedia title for the popups."""
    places = data["places"]
    chosen = choose(data, regions, by_iso, min_sitelinks)
    city_labels(chosen, places)
    city_aliases(chosen, data["aliases"], {q: c["label"] for q, c in data["cities"].items()})

    titles: dict[str, str] = {}
    region_ranks: set[str] = set()
    groups: dict[str, dict] = {}     # name -> node under construction
    kids: dict[str, list[str]] = collections.defaultdict(list)

    def group(name: str, label: str, rank: str | None, parent: str | None, title: str | None) -> str:
        if name not in groups:
            groups[name] = {"name": name, "label": label, "rank": rank}
            if parent is not None:
                kids[parent].append(name)
            if title:
                titles[name] = title
        return name

    def place_title(k: str) -> str:
        p = places.get(k, {})
        return p.get("title") or p.get("label") or k

    leaves: dict[str, dict] = {}
    for it in chosen:
        parent = group("World", "World", None, None, None)
        for name, rank in zip(it["chain"], ("Continent", "Subregion")):
            parent = group(name, name, rank, parent, ARTICLES.get(name, name))
        if it["country"]:
            t = place_title(it["country"])
            parent = group(t, label_of(t), "Country", parent, t)
        # A region with the city's own name is the city (Andorra la Vella's
        # parish, which has no article of its own).
        if it["region"] and place_title(it["region"]) != it["title"]:
            t = place_title(it["region"])
            rank = type_rank(data["graph"]["types"][it["region_type"]])
            region_ranks.add(rank)
            parent = group(t, label_of(t), rank, parent, t)
        leaves[it["title"]] = node(it["title"], "City-state" if it["city_state"] else "City", it["label"],
                                   aliases=it["aliases"] or None)
        kids[parent].append(it["title"])
        titles[it["title"]] = it["title"]

    clash = set(leaves) & set(groups)
    if clash:
        raise SystemExit(f"a city has a group's name: {sorted(clash)}")
    bad = sorted(r for r in region_ranks if r.casefold() in LADDER_RANKS)
    if bad:
        raise SystemExit(f"a region type reads as a ladder rank: {bad}")

    def sort_key(name: str) -> str:
        n = groups.get(name) or leaves[name]
        return fold(n.get("label", n["name"]))

    def make(name: str) -> dict:
        if name in leaves:
            return leaves[name]
        g = groups[name]
        return node(g["name"], g["rank"], g["label"],
                    children=[make(k) for k in sorted(set(kids[name]), key=sort_key)])

    root = next(n for n in groups if n not in {k for ks in kids.values() for k in ks})
    keep = {n for n, g in groups.items() if (g["rank"] or "").casefold() in LADDER_RANKS}
    return collapse_lone_children(make(root), keep), titles


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


def info_for(tree: dict, titles: dict[str, str]) -> dict[str, dict]:
    names: list[str] = []

    def walk(n: dict) -> None:
        if n["name"] in titles:
            names.append(n["name"])
        for c in n.get("children") or []:
            walk(c)
    walk(tree)
    found = summaries([titles[n] for n in names])
    return {n: e for n in names if (e := info_entry(found[titles[n]]))}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--min-sitelinks", type=int, default=MIN_SITELINKS)
    ap.add_argument("--refresh", action="store_true", help="refetch Wikidata and Natural Earth")
    args = ap.parse_args()
    if args.min_sitelinks < FETCH_FLOOR:
        raise SystemExit(f"--min-sitelinks below FETCH_FLOOR ({FETCH_FLOOR}) needs FETCH_FLOOR lowered first")
    regions, by_iso = natural_earth(args.refresh)
    data = wikidata(args.refresh)
    tree, titles = build(data, regions, by_iso, args.min_sitelinks)
    write_dataset("cities", tree, info_for(tree, titles))


if __name__ == "__main__":
    main()
