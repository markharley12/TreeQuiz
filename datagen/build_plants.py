#!/usr/bin/env python3
"""datasets/plants — well-known plants, by the tree of life.

Plantae → … → order → family → genus → species, as Wikidata's parent taxon
(P171) has them. So the tomato and the potato meet at *Solanum*, the tomato
and the sweet potato at the Solanales, the tomato and maize at the
flowering plants.

Sources:

- **Plants and their classification**: Wikidata (CC0). A plant is a species
  or a genus (P105) under *Plantae* (Q756), chosen by how many Wikipedias
  cover it (`MIN_SITELINKS`), as cities and TaxoQuiz's animals were. The
  scan for candidates goes to QLever (see `wikidata.py`), since Wikidata's
  own endpoint times out walking a million taxa; the walk up from them is
  batched there.
- **Popup text**: English Wikipedia.

Decisions:

- **A genus is a plant when it is better known than its species.** The oak
  (159 Wikipedias) is a leaf and its species are dropped, since *Quercus
  robur* has 86; *Citrus* (112) is a group, since the lemon has 186. A genus
  with no species chosen is a leaf whatever its count: the rose, the tulip.
  The same rule runs at every level, so a taxon is a leaf exactly when it is
  better known than everything chosen below it.
- **One parent each: the deepest.** Some taxa have two P171s, an older
  classification beside a newer, or a family beside the genus; the parent
  with the longer way up to Plantae wins, being the more resolved, and ties
  go to the lower QID. A loop is refused.
- **Names are scientific, labels English.** A node's name is its taxon name
  (P225), which `checks.closer` uses and a relabel cannot break. A leaf's
  label is, first that applies:
    1. `LABELS`, by hand;
    2. its English Wikipedia title less any "(plant)", unless that is a
       taxon name anywhere on Wikidata (*Olea europaea* is; "Sorghum" is,
       as the genus, for the species);
    3. its English Wikidata label, on the same terms;
    4. its taxon name, where an English common name (P1843) is the same
       word — magnolia, dahlia, iris;
    5. its one English common name, where it has exactly one.
  Anything else fails the build until `LABELS` names it, as instruments do
  with relative names: every leaf reads in English, as every animal does.
  Rule 5 is the weakest (P1843 gave *Vitis vinifera* "wild grape"), so the
  build prints what it chose for review. Groups keep their scientific names,
  as the animals' do; their popups say what they are.
- **Title Case is lowered**: common names come from many databases, and
  "Scots Pine" sat beside "Scots pine". In a name whose every word is
  capitalised, only the first keeps its capital; every label starts with
  one.
- **A plant needs a scientific name.** Wikidata's kumquat is a group known
  by a common name, filed as a genus with "citrus fruit" for its taxon name;
  a P225 must start with a capital or "×".
- **Aliases** are a leaf's scientific names, title, Wikidata label and
  common names, less any that is another leaf's label or that two leaves
  claim.
- **Pass-throughs are spliced**, as every builder does, and a run of them
  is shown by its best-known member: the pea subfamily is *Faboideae*
  (55 Wikipedias), not the *Meso-Papilionoideae* clade (1) that holds the
  same plants.

Usage:
    python3 datagen/build_plants.py [--min-sitelinks 55] [--refresh]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import unicodedata

from common import CACHE, collapse_lone_children, node, write_dataset
from wikidata import QLEVER, batched, qid, qlever, title
from wikipedia import info_entry, summaries

MIN_SITELINKS = 55
FETCH_FLOOR = 40      # candidates are fetched down to here, so tuning needs no refetch
PLANTAE = "Q756"
LEAF_RANKS = {"Q7432": "species", "Q34740": "genus"}
CANDIDATES = """SELECT ?c ?sl WHERE {
  ?c wdt:P105 wd:%s ; wikibase:sitelinks ?sl . FILTER(xsd:integer(?sl) >= %d)
  ?c wdt:P171+ wd:Q756 .
}"""
TAXA = """SELECT ?x ?up ?rank ?name ?l ?enwiki ?sl WHERE {
  VALUES ?x { %s }
  ?x wikibase:sitelinks ?sl .
  OPTIONAL { ?x wdt:P171 ?up }
  OPTIONAL { ?x wdt:P105 ?rank }
  OPTIONAL { ?x wdt:P225 ?name }
  OPTIONAL { ?x rdfs:label ?l FILTER(lang(?l) = "en") }
  OPTIONAL { ?enwiki schema:about ?x ; schema:isPartOf <https://en.wikipedia.org/> }
}"""
COMMON = """SELECT ?x ?cn WHERE { VALUES ?x { %s } ?x wdt:P1843 ?cn FILTER(lang(?cn) = "en") }"""
RANK_NAMES = """SELECT ?x ?l WHERE { VALUES ?x { %s } ?x rdfs:label ?l FILTER(lang(?l) = "en") }"""
# Which of some strings are taxon names somewhere on Wikidata.
IS_TAXON = """SELECT DISTINCT ?n WHERE { VALUES ?n { %s } ?x wdt:P225 ?n }"""

# Taxon name -> its parent's, where Wikidata's best-known parent is an older
# classification's. The parent need not be one Wikidata gives: Ebenaceae has
# only Cronquist's Ebenales, which put the persimmon among no other plant here.
PARENTS: dict[str, str] = {
    "Ebenaceae": "Ericales",
    # Ruscus is in Asparagaceae's Nolinoideae; Wikidata has Solanaceae's
    # Nolanoideae.
    "Ruscus": "Asparagaceae",
    # The apples sit in the old subfamily Maloideae, the pear in the tribe
    # Maleae that replaced it, the quince in neither.
    **dict.fromkeys(["Amelanchier", "Cotoneaster", "Crataegus", "Cydonia", "Malus", "Mespilus", "Pyrus", "Sorbus"],
                    "Malinae"),
    "Mutisieae": "Mutisioideae", "Tagetes": "Asteroideae",
    # The ferns' only parent is the old Pteridophyta, under the land plants,
    # where they would meet the seed plants no lower than the mosses do.
    "Polypodiopsida": "Tracheophytes",
    # Wikidata has two gymnosperm items; the conifers and gnetophytes were
    # under one, the ginkgo under the other.
    "Pinophyta": "Gymnospermae", "Gnetophyta": "Gymnospermae",
}

# Taxon name -> label, where the rules give none (a title that is only the
# Latin, several common names) or a poor one (P1843's "wild grape" for the
# grapevine, plurals, "pepper" for Capsicum beside black pepper). Written
# from the plant's English Wikipedia lead.
LABELS: dict[str, str] = {
    # no label by rule
    "Achillea millefolium": "Yarrow", "Acorus calamus": "Sweet flag", "Adiantum capillus-veneris": "Maidenhair fern",
    "Aegle marmelos": "Bael", "Agave": "Agave", "Agrostemma githago": "Corncockle", "Ailanthus altissima": "Tree of heaven",
    "Allium ursinum": "Wild garlic", "Aloe": "Aloe", "Althaea officinalis": "Marsh mallow",
    "Angelica archangelica": "Garden angelica", "Arctostaphylos uva-ursi": "Bearberry", "Argania spinosa": "Argan",
    "Artemisia absinthium": "Wormwood", "Artemisia vulgaris": "Mugwort", "Azadirachta indica": "Neem",
    "Bellis perennis": "Common daisy", "Berberis vulgaris": "Barberry", "Bixa orellana": "Achiote",
    "Brassica juncea": "Brown mustard", "Brassica oleracea": "Cabbage", "Brassica rapa": "Turnip", "Buxus": "Boxwood",
    "Calluna vulgaris": "Heather", "Caltha palustris": "Marsh marigold", "Camellia sinensis": "Tea plant",
    "Cananga odorata": "Ylang-ylang", "Carex": "Sedge", "Cassia fistula": "Golden shower tree",
    "Centaurium erythraea": "Common centaury", "Centella asiatica": "Gotu kola", "Chamaenerion angustifolium": "Fireweed",
    "Chenopodium album": "Fat hen", "Chrysopogon zizanioides": "Vetiver", "Clematis": "Clematis",
    "Clitoria ternatea": "Butterfly pea", "Colchicum autumnale": "Autumn crocus", "Conium maculatum": "Hemlock",
    "Cornus mas": "Cornelian cherry", "Corylus avellana": "Hazel", "Cuscuta": "Dodder", "Cyperus rotundus": "Nutgrass",
    "Datura stramonium": "Jimsonweed", "Delonix regia": "Royal poinciana", "Diospyros kaki": "Japanese persimmon",
    "Dryopteris filix-mas": "Male fern", "Echium vulgare": "Viper's bugloss", "Ficus benghalensis": "Banyan",
    "Ficus elastica": "Rubber fig", "Filipendula ulmaria": "Meadowsweet", "Ginkgo biloba": "Ginkgo",
    "Hevea brasiliensis": "Rubber tree", "Humulus lupulus": "Hop", "Hyoscyamus niger": "Henbane",
    "Hypericum perforatum": "St John's wort", "Ilex aquifolium": "Holly", "Illicium verum": "Star anise",
    "Lathyrus": "Vetchling", "Leucanthemum vulgare": "Oxeye daisy", "Mangifera indica": "Mango",
    "Matricaria chamomilla": "Chamomile", "Melia azedarach": "Chinaberry", "Melilotus officinalis": "Yellow sweet clover",
    "Mirabilis jalapa": "Four o'clock flower", "Morinda citrifolia": "Noni", "Narcissus": "Daffodil",
    "Nigella sativa": "Black cumin", "Nuphar lutea": "Yellow water-lily", "Olea europaea": "Olive",
    "Opuntia": "Prickly pear", "Orchis": "Orchis", "Oxalis acetosella": "Wood sorrel",
    "Oxalis corniculata": "Creeping wood sorrel", "Papaver rhoeas": "Common poppy", "Passiflora edulis": "Passion fruit",
    "Persicaria hydropiper": "Water pepper", "Persicaria maculosa": "Redshank", "Pistacia lentiscus": "Mastic tree",
    "Polygonum aviculare": "Knotgrass", "Portulaca oleracea": "Purslane", "Potentilla erecta": "Tormentil",
    "Primula": "Primrose", "Prunus avium": "Sweet cherry", "Prunus cerasifera": "Cherry plum",
    "Prunus padus": "Bird cherry", "Prunus spinosa": "Blackthorn", "Rafflesia": "Rafflesia",
    "Ranunculus": "Buttercup", "Rhamnus cathartica": "Common buckthorn", "Ribes uva-crispa": "Gooseberry",
    "Robinia pseudoacacia": "Black locust", "Rubus chamaemorus": "Cloudberry", "Rumex acetosella": "Sheep's sorrel",
    "Ruscus aculeatus": "Butcher's broom", "Asparagus officinalis": "Asparagus", "Ricinus communis": "Castor oil plant",
    "Menyanthes trifoliata": "Bogbean", "Cinnamomum camphora": "Camphor tree", "Oryza sativa": "Rice",
    "Citrus ×sinensis": "Orange", "Linum usitatissimum": "Flax", "Cryptomeria japonica": "Japanese cedar",
    "Canna": "Canna", "Myrtus communis": "Myrtle", "Salvia hispanica": "Chia", "Salvia officinalis": "Sage",
    "Saxifraga": "Saxifrage", "Silene vulgaris": "Bladder campion", "Solanum dulcamara": "Bittersweet nightshade",
    "Sonchus oleraceus": "Sow thistle", "Stellaria media": "Chickweed", "Symphytum officinale": "Comfrey",
    "Syzygium cumini": "Java plum", "Taxus baccata": "Yew", "Tilia": "Linden", "Tribulus terrestris": "Puncturevine",
    "Vaccinium myrtillus": "Bilberry", "Vanilla": "Vanilla", "Verbena officinalis": "Vervain", "Veronica": "Speedwell",
    "Viburnum opulus": "Guelder rose", "Vicia sativa": "Common vetch", "Vinca minor": "Lesser periwinkle",
    "Viscum album": "Mistletoe", "Welwitschia mirabilis": "Welwitschia", "Yucca": "Yucca",
    # a poor one by rule
    "Abrus precatorius": "Rosary pea", "Aesculus hippocastanum": "Horse chestnut", "Anthurium": "Anthurium",
    "Apium graveolens": "Celery", "Areca catechu": "Areca palm", "Arbutus unedo": "Strawberry tree",
    "Arctium lappa": "Burdock", "Averrhoa carambola": "Starfruit", "Beta vulgaris": "Beet",
    "Borassus flabellifer": "Palmyra palm", "Boehmeria nivea": "Ramie", "Campanula": "Bellflower",
    "Cannabis": "Cannabis", "Capsicum": "Capsicum", "Cercis siliquastrum": "Judas tree",
    "Chrysanthemum": "Chrysanthemum", "Cucurbita": "Squash", "Cymbopogon": "Lemongrass", "Cynodon dactylon": "Bermuda grass",
    "Cyperus papyrus": "Papyrus", "Daucus carota": "Carrot", "Delphinium": "Delphinium", "Dianthus": "Dianthus",
    "Digitalis": "Foxglove", "Drosera": "Sundew", "Elaeis guineensis": "Oil palm", "Elymus repens": "Couch grass",
    "Ephedra": "Ephedra", "Eucalyptus": "Eucalyptus", "Ficus religiosa": "Sacred fig", "Geranium": "Cranesbill",
    "Gerbera": "Gerbera", "Hedera helix": "Ivy", "Heracleum": "Hogweed", "Hibiscus": "Hibiscus",
    "Indigofera tinctoria": "Indigo", "Juglans regia": "Walnut", "Kalanchoe": "Kalanchoe", "Laurus nobilis": "Bay laurel",
    "Momordica charantia": "Bitter melon", "Nepenthes": "Pitcher plant", "Nicotiana tabacum": "Tobacco",
    "Nymphaea": "Water lily", "Pelargonium": "Pelargonium", "Phaseolus vulgaris": "Common bean",
    "Phyllanthus emblica": "Indian gooseberry", "Physalis": "Physalis", "Platanus": "Plane tree",
    "Prunus domestica": "Plum", "Ruta graveolens": "Rue", "Silybum marianum": "Milk thistle", "Typha": "Cattail",
    "Vaccinium vitis-idaea": "Lingonberry",
}


# --- fetching ---------------------------------------------------------------

def wikidata(refresh: bool) -> dict:
    """Everything the build reads from Wikidata, fetched once at FETCH_FLOOR."""
    path = CACHE / "plants" / f"wikidata-{FETCH_FLOOR}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    candidates: dict[str, int] = {}
    for rank in LEAF_RANKS:
        for b in qlever(CANDIDATES % (rank, FETCH_FLOOR)):
            candidates[qid(b, "c")] = int(b["sl"]["value"])
    print(f"wikidata: {len(candidates)} species and genera at {FETCH_FLOOR}+ sitelinks")
    taxa: dict[str, dict] = {}
    todo = set(candidates)
    while todo:
        print(f"  walking up: {len(todo)} taxa")
        for b in batched(TAXA, sorted(todo)):
            t = taxa.setdefault(qid(b, "x"), {"up": [], "rank": None, "names": [], "label": None,
                                              "title": None, "sitelinks": int(b["sl"]["value"])})
            up = qid(b, "up")
            if up and up not in t["up"]:
                t["up"].append(up)
            t["rank"] = t["rank"] or qid(b, "rank")
            name = b.get("name", {}).get("value")
            if name and name not in t["names"]:
                t["names"].append(name)
            t["label"] = t["label"] or b.get("l", {}).get("value")
            t["title"] = t["title"] or title(b)
        todo = {u for q, t in taxa.items() if q != PLANTAE for u in t["up"]} - set(taxa)
    common: dict[str, list[str]] = collections.defaultdict(list)
    for b in batched(COMMON, sorted(candidates)):
        common[qid(b, "x")].append(b["cn"]["value"])
    ranks = {qid(b, "x"): b["l"]["value"]
             for b in batched(RANK_NAMES, sorted({t["rank"] for t in taxa.values() if t["rank"]}))}
    words = sorted({bare(s) for q in candidates for s in (taxa[q]["title"], taxa[q]["label"]) if s})
    taxon_names = sorted({b["n"]["value"] for b in batched(IS_TAXON, words, literal=True, endpoint=QLEVER)})
    data = {"candidates": candidates, "taxa": taxa, "common": common, "ranks": ranks,
            "taxon_names": taxon_names}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True))
    return data


# --- the classification -----------------------------------------------------

def heights(taxa: dict) -> dict[str, int]:
    """Each taxon's longest way up to Plantae, for those that get there. A
    parent already on the way (a loop) is not a way up."""
    memo: dict[str, int | None] = {PLANTAE: 0}

    def height(q: str, path: frozenset) -> int | None:
        if q in memo:
            return memo[q]
        if q in path or q not in taxa:
            return None
        ups = [h for u in taxa[q]["up"] if (h := height(u, path | {q})) is not None]
        memo[q] = max(ups) + 1 if ups else None
        return memo[q]

    for q in taxa:
        height(q, frozenset())
    return {q: h for q, h in memo.items() if h is not None}


def ancestors(taxa: dict) -> dict[str, set[str]]:
    """Everything above each taxon, by any of its parents."""
    memo: dict[str, set[str]] = {}

    def up(q: str, path: frozenset) -> set[str]:
        if q in memo:
            return memo[q]
        out: set[str] = set()
        for u in taxa.get(q, {}).get("up", []):
            if u not in path:
                out |= {u} | up(u, path | {q})
        memo[q] = out
        return out

    for q in taxa:
        up(q, frozenset())
    return memo


def qorder(q: str) -> tuple[int, str]:
    """QIDs in numeric order: Q9 before Q10."""
    return len(q), q


def parents(taxa: dict) -> dict[str, str]:
    """Each taxon's one parent: `PARENTS`'s; else, of those that reach
    Plantae and are not above another of them, the one most Wikipedias
    cover, then the lowest QID. *Astereae* has both *Asteraceae* and
    *Asteroideae* within it, and the second says more."""
    h = heights(taxa)
    above = ancestors(taxa)
    by_name = {taxon_name(q, t): q for q, t in taxa.items()}
    unknown = sorted(p for p in PARENTS.values() if by_name.get(p) not in h)
    if unknown:
        raise SystemExit(f"PARENTS names taxa not under Plantae here: {unknown}")
    out = {}
    for q, t in taxa.items():
        ups = [u for u in t["up"] if u in h]
        if q == PLANTAE or q not in h or not ups:
            continue
        ups = [u for u in ups if not any(u in above[v] for v in ups if v != u)] or ups
        fixed = PARENTS.get(taxon_name(q, t))
        out[q] = by_name[fixed] if fixed else min(ups, key=lambda u: (-taxa[u]["sitelinks"], qorder(u)))
    return out


# A scientific name starts with a capital, or the hybrid sign.
LATIN = re.compile(r"[A-Z×]")


def lineage(q: str, parent: dict[str, str]) -> list[str]:
    """`q` and everything above it, up to Plantae."""
    out = [q]
    while out[-1] != PLANTAE:
        up = parent[out[-1]]
        if up in out:
            raise SystemExit(f"a loop in Wikidata's parent taxa: {out + [up]}")
        out.append(up)
    return out


def choose(data: dict, parent: dict[str, str], min_sitelinks: int) -> list[str]:
    """The leaves: candidates at `min_sitelinks`, each kept if it is better
    known than every candidate below it, whose place it then takes."""
    sitelinks = data["candidates"]
    chosen = {q for q, n in sitelinks.items()
              if n >= min_sitelinks and q in parent and any(LATIN.match(n) for n in data["taxa"][q]["names"])}
    above = {q: lineage(q, parent)[1:] for q in chosen}
    below: dict[str, list[str]] = collections.defaultdict(list)
    for q in chosen:
        for a in above[q]:
            if a in chosen:
                below[a].append(q)
    leaves, dropped = [], set()
    for q in sorted(chosen, key=lambda q: (len(above[q]), qorder(q))):     # top down
        if q in dropped:
            continue
        rest = [k for k in below[q] if k not in dropped]
        if sitelinks[q] > max((sitelinks[k] for k in rest), default=0):
            leaves.append(q)
            dropped.update(rest)
    return sorted(leaves, key=qorder)


# --- names ------------------------------------------------------------------

def sci(s: str) -> str:
    """A name compared as a name: "Citrus × sinensis" is "Citrus ×sinensis"."""
    return re.sub(r"\s*×\s*", "×", s).casefold()


def bare(s: str) -> str:
    """A title less its disambiguation: "Iris (plant)" -> "Iris"."""
    return re.sub(r" \([^)]*\)$", "", s)


def tidy(s: str) -> str:
    """Title Case lowered after the first word: "Scots Pine" -> "Scots pine"."""
    words = s.split(" ")
    if len(words) > 1 and all(w[:1].isupper() for w in words):
        return " ".join([words[0], *(w[:1].lower() + w[1:] for w in words[1:])])
    return s


def taxon_name(q: str, t: dict) -> str:
    """The taxon's name: its P225, the one its title or label uses where it
    has several; else its English label (a clade may have no P225)."""
    names = sorted(t["names"])
    for s in (t["title"], t["label"]):
        if s and bare(s) in names:
            return bare(s)
    return names[0] if names else t["label"] or t["title"] or q


def leaf_label(q: str, data: dict) -> tuple[str | None, str]:
    """(label, the rule that gave it) — None where no rule does."""
    t = data["taxa"][q]
    name = taxon_name(q, t)
    if name in LABELS:
        return LABELS[name], "by hand"
    scientific = {sci(n) for n in [*data["taxon_names"], *t["names"]]}
    for s, how in ((t["title"], "title"), (t["label"], "label")):
        if s and sci(bare(s)) not in scientific:
            return tidy(bare(s)), how
    common = list({tidy(c.strip()).casefold(): tidy(c.strip()) for c in data["common"].get(q, [])}.values())
    if any(c.casefold() == name.casefold() for c in common):
        return name, "used in English"
    if len(common) == 1:
        return common[0], "common name"
    return None, "none"


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


ALIAS = re.compile(r"[A-Za-z][A-Za-z ×.'’-]*")


def aliases_for(leaves: list[str], data: dict, labels: dict[str, str]) -> dict[str, list[str]]:
    """Scientific names, title, Wikidata label and common names, less any
    that is another leaf's label or that two leaves claim."""
    taken = {fold(lab) for lab in labels.values()}
    found: dict[str, list[str]] = {}
    owners: collections.Counter = collections.Counter()
    for q in leaves:
        t = data["taxa"][q]
        seen, out = {fold(labels[q])}, []
        for a in [*sorted(t["names"]), t["title"] and bare(t["title"]), t["label"], *sorted(data["common"].get(q, []))]:
            a = tidy((a or "").strip())
            if not a or len(a) > 40 or not ALIAS.fullmatch(a) or re.search(r"(.)\1\1", a) or fold(a) in seen:
                continue
            seen.add(fold(a))
            out.append(a)
        found[q] = out
        owners.update({fold(a) for a in out})
    return {q: [a for a in out if fold(a) not in taken and owners[fold(a)] == 1] for q, out in found.items()}


# --- building ---------------------------------------------------------------

def build(data: dict, min_sitelinks: int) -> tuple[dict, dict[str, str]]:
    """The tree, and node name to Wikipedia title for the popups."""
    taxa = data["taxa"]
    parent = parents(taxa)
    leaves = choose(data, parent, min_sitelinks)

    labels: dict[str, str] = {}
    missing, review = [], []
    for q in leaves:
        lab, how = leaf_label(q, data)
        if lab is None:
            missing.append(f"{taxon_name(q, taxa[q])} ({q}): {sorted(set(data['common'].get(q, [])))}")
        else:
            labels[q] = lab[:1].upper() + lab[1:]
            if how == "common name":
                review.append(f"{taxon_name(q, taxa[q])} -> {lab}")
    if review:
        print(f"labelled by their one common name ({len(review)}), for review:\n  " + "\n  ".join(review))
    if missing:
        raise SystemExit(f"{len(missing)} plants need a label in LABELS:\n  " + "\n  ".join(missing))
    clash = [lab for lab, n in collections.Counter(fold(v) for v in labels.values()).items() if n > 1]
    if clash:
        raise SystemExit(f"two plants share a label (set LABELS): {sorted(clash)}")
    aliases = aliases_for(leaves, data, labels)

    names = {q: taxon_name(q, taxa[q]) for q in {a for q in leaves for a in lineage(q, parent)}}
    dup = [n for n, k in collections.Counter(names.values()).items() if k > 1]
    if dup:
        raise SystemExit(f"two taxa share a name: {sorted(dup)}")
    kids: dict[str, set[str]] = collections.defaultdict(set)
    for q in leaves:
        line = lineage(q, parent)
        for child, up in zip(line, line[1:]):
            kids[up].add(child)

    def rank(q: str) -> str | None:
        r = data["ranks"].get(taxa[q]["rank"] or "")
        return r[:1].upper() + r[1:] if r else None

    def label(q: str) -> str:
        return labels.get(q, names[q])

    def make(q: str) -> dict:
        if q in labels:
            return node(names[q], rank(q), labels[q], aliases=aliases[q] or None)
        return node(names[q], rank(q), children=[make(k) for k in sorted(kids[q], key=lambda k: fold(label(k)))])

    titles = {names[q]: taxa[q]["title"] for q in names if taxa[q]["title"]}
    fame = {names[q]: taxa[q]["sitelinks"] for q in names}
    return collapse_lone_children(make(PLANTAE), prefer=lambda n: fame[n["name"]]), titles


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
    ap.add_argument("--refresh", action="store_true", help="refetch Wikidata")
    args = ap.parse_args()
    if args.min_sitelinks < FETCH_FLOOR:
        raise SystemExit(f"--min-sitelinks below FETCH_FLOOR ({FETCH_FLOOR}) needs FETCH_FLOOR lowered first")
    tree, titles = build(wikidata(args.refresh), args.min_sitelinks)
    write_dataset("plants", tree, info_for(tree, titles))


if __name__ == "__main__":
    main()
