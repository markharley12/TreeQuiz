#!/usr/bin/env python3
"""datasets/instruments — musical instruments, on the Hornbostel–Sachs tree.

Hornbostel–Sachs (1914) classifies an instrument by how it makes its sound, as
a decimal code in which every digit is a step down a tree: `3` chordophones,
`32` composite chordophones, `321` lutes, `321.322` necked box lutes. So the
code *is* the instrument's lineage, and a violin and a guitar share 321.322
while a violin and a piano share only 3. Suffixes after a dash say how the
instrument is played: `-71` with a bow.

Sources:

- **Which instruments, and their codes**: Wikidata (CC0) — every item with a
  Hornbostel–Sachs number (P1762), chosen by how many Wikipedias cover it, as
  TaxoQuiz chose species. `MIN_SITELINKS` sets the bar. English alternative
  labels become aliases, so "French horn" finds the horn.
- **What each code is called**: English Wikipedia (CC BY-SA 4.0). The four
  *List of …phones by Hornbostel–Sachs number* articles name every code in
  their class, and win where they disagree with the *Hornbostel–Sachs* article,
  which is used for the five classes and the rest. They win because they are
  the numbering Wikidata uses: the main article puts goblet drums at 211.25 and
  calls 423.233 "sets of slide trumpets", where the list has conical drums and
  cylindrical bore, and Wikidata files the ashiko at 211.251 and the trumpet at
  423.233.
- **Suffixes**: the chordophone and membranophone lists define them.
  Aerophone and idiophone suffixes are not defined on Wikipedia, so those
  instruments sit at their base code rather than under a suffix named by guess.
- **Electrophones** (`ELECTROPHONES`): Wikidata numbers them by the 2011 MIMO
  revision (the electric guitar is 513, the Hammond organ 521), which no
  Wikipedia article lists. Sachs's 1940 names, which the main article gives,
  would file the electric guitar under "electric action", so the names here
  are TreeQuiz's own short descriptions of the revised classes.

Decisions:

- **An item with several codes takes the most specific**, longest base first,
  then longest suffix. The tambourine is both a shaken idiophone (112.1) and a
  frame drum (211.311); either is defensible, and "first statement Wikidata
  returned" — TaxoQuiz's most expensive habit — would not be.
- **A code of one or two digits is a category, not an instrument**: "drum"
  (21) and "wind instrument" (42) are left out, and so is `EXCLUDE`.
- **A compound code** (the pipe organ's `421.222.11+421.222.3+412.1`) uses its
  first part.
- **A few codes are corrected** (`CODE_FIXES`), each with its evidence. They
  are upstream errors, worth fixing on Wikidata too.
- **Class names are tidied for reading out of context** (`tidy`, `LABELS`).
  The articles name a class relative to its parent ("With fingerholes",
  "Single instruments"), which is fine in an indented list and meaningless in
  a guess's lineage. The build fails on a relative or overlong name it has no
  label for, so a new threshold that surfaces a new class asks for one.
- **No ladder.** A digit is a step, but the steps are not equally specific in
  every branch; the tree's shape places them, as with languages.

Usage:
    python3 datagen/build_instruments.py [--min-sitelinks 12] [--refresh]
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import urllib.parse
import urllib.request

from common import CACHE, USER_AGENT, collapse_lone_children, fetch, node, write_dataset
from wikipedia import info_entry, summaries, title_from_url

MIN_SITELINKS = 12
WIKI = "https://en.wikipedia.org/w/index.php?action=raw&title="
ARTICLE = "Hornbostel%E2%80%93Sachs"
LISTS = {
    "1": "List_of_idiophones_by_Hornbostel%E2%80%93Sachs_number",
    "2": "List_of_membranophones_by_Hornbostel%E2%80%93Sachs_number",
    "3": "List_of_chordophones_by_Hornbostel%E2%80%93Sachs_number",
    "4": "List_of_aerophones_by_Hornbostel%E2%80%93Sachs_number",
}
SPARQL = """SELECT ?item ?hs ?sl ?label ?enwiki WHERE {
  ?item wdt:P1762 ?hs ; wikibase:sitelinks ?sl .
  OPTIONAL { ?item rdfs:label ?label FILTER(lang(?label) = "en") }
  OPTIONAL { ?enwiki schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
}"""
ALIASES_SPARQL = """SELECT ?item ?alt WHERE {
  ?item wdt:P1762 [] ; skos:altLabel ?alt FILTER(lang(?alt) = "en")
}"""

# Upstream errors, each checked by hand. Keyed by item, not by code, so a fix
# that has reached Wikidata is simply never consulted again.
CODE_FIXES = {
    # A button accordion. 421.221 is a duct flute; Wikipedia's infobox has 412.132.
    "Q804099": "412.132",
    # "314-122-5" mistypes a dot as a dash; Wikipedia's article has 314.122-5.
    "Q2145031": "314.122-5",
    # Plays by plucking a steel comb, a comb lamellophone (122); Wikidata's
    # 112.1 files it with the rattles.
    "Q1365218": "122",
}

# Items with a code that are not one instrument.
EXCLUDE = {
    "Q180744",    # brass instrument: a family by material, coded 423 like every trumpet
    "Q1365097",   # violin family: the violin, viola and cello are all here themselves
    "Q64166304",  # electric bass guitar: the same instrument as bass guitar (Q46185)
}

# Names only: a gloss here would be TreeQuiz's words, and the popup credits
# its text to Wikipedia.
ELECTROPHONES = {
    "51": "Electro-acoustic instruments",
    "511": "Electro-acoustic idiophones",
    "513": "Electro-acoustic chordophones",
    "52": "Electromechanical instruments",
    "521": "Tonewheel instruments",
    "524": "Tape replay instruments",
    "53": "Analogue electronic instruments",
    "531": "Analogue electronic instruments",
    "54": "Digital instruments",
    "541": "Digital synthesizers",
}

# Names the articles give relative to a parent, as a sentence, or with a
# typo. Only codes some instrument reaches need one; `check_labels` says which.
LABELS = {
    "111212": "Xylophones",
    "11124211": "Resting bells",
    "11124212": "Hanging bells",
    "11124222": "Sets of hanging bells",
    "111242222": "Sets of bells with internal strikers",
    "1121": "Rattles",
    "1122": "Scraped idiophones",
    "122": "Comb lamellophones",
    "21111": "Kettle drums",
    "211212": "Double-headed cylindrical drums",
    "2112121": "Single double-headed drums",
    "2112211": "Open-ended barrel drums",
    "21124": "Hourglass drums",
    "211251": "Single-headed conical drums",
    "211261": "Single-headed goblet drums",
    "211311": "Single-headed frame drums",
    "314122": "Board zithers with resonator box",
    "32221": "Frame harps without tuning action",
    "41213": "Free-reed instruments",
    "4122": "Interruptive aerophones without a reed",
    "42": "Wind instruments",
    "42111112": "End-blown flutes with fingerholes",
    "42112112": "Side-blown flutes with fingerholes",
    "42121112": "External-duct flutes with fingerholes",
    "42122111": "Duct flutes without fingerholes",
    "42122112": "Duct flutes with fingerholes",
    "42122142": "Vessel duct flutes with fingerholes",
    "42122211": "Sets of duct flutes (organ pipes)",
    "422111": "Oboes with cylindrical bore",
    "4221112": "Cylindrical oboes with fingerholes",
    "422112": "Oboes with conical bore",
    "422211": "Clarinets with cylindrical bore",
    "4222112": "Cylindrical clarinets with fingerholes",
    "422212": "Clarinets with conical bore",
    "42311": "Conches",
    "42312111": "Straight trumpets without mouthpiece",
    "42312112": "Straight trumpets with mouthpiece",
    "42312122": "Horns with mouthpiece",
    "423232": "Valved brass with semi-conical bore",
    "423233": "Valved brass with cylindrical bore",
}

# Suffix groups used as nodes, and what they are called there. The source's
# words are checked to still define each, and go in the popup.
SUFFIXES = {
    "3": {"4": "Struck with hammers", "5": "Plucked with fingers", "6": "Plucked with a plectrum",
          "7": "Bowed", "71": "Bowed with a bow", "72": "Bowed with a wheel", "8": "With a keyboard",
          "9": "Mechanically played"},
    "2": {"6": "Membrane glued on", "7": "Membrane nailed on", "8": "Membrane laced on",
          "9": "Membrane held by a ring"},
}
SUFFIX_RANK = {"3": "Played", "2": "Membrane"}
SUFFIX_NOUN = {"3": "chordophone", "2": "membranophone"}

_LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
_FIRST_LINK = re.compile(r"\[\[([^\]|#]+)")
_RELATIVE = re.compile(r"^(with|without|single instruments|instruments|((semi-)?conical|cylindrical|regular|irregular) bore)\b", re.I)
MAX_LABEL = 40


def plain(wikitext: str) -> str:
    """Wiki markup to text: links to their shown text, emphasis and refs dropped."""
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", wikitext)
    s = _LINK.sub(r"\1", s)
    s = re.sub(r"'{2,}", "", s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = s.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", s).strip()


def parse_classes(wikitext: str, only: str = "") -> dict[str, dict]:
    """Code digits to {name, gloss, link}, from an article's headings and from
    its code lines, bulleted or not. `only` keeps codes in one class, so a list
    article's prose cannot pass for a code.

    A heading's gloss is the paragraph under it, and its link the article a
    `{{main|…}}` names there: "==Idiophones (1)==" is followed by both."""
    out: dict[str, dict] = {}
    heading = ""
    for line in wikitext.splitlines():
        h = re.match(r"^(=+)\s*(.*?)\s*\((\d+)\)\s*\1\s*$", line)
        if h:
            digits, text, gloss = h.group(3), h.group(2), ""
        else:
            m = re.match(r"^(?:\*+\s*)?(\()?(?:\[\[[^\]|]*\|)?(\d[\d.]*)(?:\]\])?\s+(.*)$", line)
            if not m:
                if heading in out and line.strip() and not line.startswith(("*", "=", ":")):
                    main = re.match(r"^\{\{main\|([^}|]+)", line, re.I)
                    if main and not out[heading]["link"]:
                        out[heading]["link"] = main.group(1).strip()
                    elif not line.startswith("{{") and not out[heading]["gloss"]:
                        out[heading]["gloss"] = plain(line)
                elif line.startswith(("*", "=")):
                    heading = ""
                continue
            digits = m.group(2).replace(".", "")
            text = m.group(3)
            if m.group(1):  # "(422.112 With irregular bore.)": the whole line is bracketed
                text = re.sub(r"\)\s*$", "", text)
            # "Bells – The vibration is weakest near the vertex": name, then gloss.
            parts = re.split(r"\s+[–—-](?:\s+|$)", text, maxsplit=1)
            text, gloss = parts[0], parts[1] if len(parts) > 1 else ""
        heading = ""
        if not digits.isdigit() or (only and not digits.startswith(only)):
            continue
        if h and digits not in out:
            heading = digits
        link = _FIRST_LINK.search(text)
        out.setdefault(digits, {
            "name": plain(text).rstrip(" .;-"),
            "gloss": plain(gloss).rstrip(" "),
            "link": link.group(1).strip() if link else "",
        })
    return out


def parse_suffixes(wikitext: str) -> dict[str, str]:
    """Suffix digits to meaning, from a list article's suffix section."""
    out: dict[str, str] = {}
    section = wikitext.split("suffix", 1)[-1] if "suffix" in wikitext else ""
    for line in section.splitlines():
        m = re.match(r"^\*+\s*'''(\d+)''':\s*(.*)$", line)
        if m:
            out[m.group(1)] = plain(m.group(2)).rstrip(" .")
        elif line.startswith("=="):
            break
    return out


def tidy(name: str) -> str:
    """A class name as a reader meets it out of context.

    "Instruments in which the body is tubular (tubular drums)" is a definition
    with the name in brackets, so the bracket is the name. Other brackets are
    examples ("(clapstick)") and go. Words after the first are sentence case:
    the articles capitalise at random ("Shaken Idiophones").
    """
    m = re.match(r"^Instruments (?:in )?which.*\(([^()]+)\)?\s*$", name)
    if m:
        name = m.group(1)
    name = re.sub(r"^\((\w+)\)\s*", r"\1 ", name)
    name = re.sub(r"\s*\([^()]*\)?\s*$", "", name)
    name = re.sub(r"\s*\([^()]*\)", "", name)
    words = name.strip(" .;-").split(" ")
    words = [words[0][:1].upper() + words[0][1:]] + [
        w.lower() if w[:1].isupper() and w[1:].islower() else w for w in words[1:]]
    return " ".join(words)


def parse_code(code: str) -> tuple[str, str]:
    """`321.322-71` to ('321322', '71'); the first part of a compound code; the
    first suffix where several are given ('5-6' is fingers or plectrum)."""
    first = code.split("+")[0].strip()
    base, _, rest = first.partition("-")
    digits = re.sub(r"[^\d]", "", base)
    suffix = re.match(r"\d*", rest.strip()).group(0) if rest else ""
    return digits, suffix


def code_text(digits: str) -> str:
    """'321322' to '321.322', as the codes are written."""
    return ".".join([digits[:3], *[digits[i:i + 3] for i in range(3, len(digits), 3)]])


def fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.casefold()) if not unicodedata.combining(c))


def _sparql(query: str, path, refresh: bool) -> list[dict]:
    if refresh or not path.exists():
        url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query})
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"})
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=300) as resp:
            path.write_bytes(resp.read())
    return json.loads(path.read_text())["results"]["bindings"]


def wikidata(refresh: bool) -> list[dict]:
    items: dict[str, dict] = {}
    for b in _sparql(SPARQL, CACHE / "instruments" / "wikidata.json", refresh):
        qid = b["item"]["value"].rsplit("/", 1)[1]
        it = items.setdefault(qid, {
            "qid": qid, "sitelinks": int(b["sl"]["value"]), "codes": set(), "aliases": [],
            "label": b.get("label", {}).get("value", ""), "enwiki": b.get("enwiki", {}).get("value", ""),
        })
        it["codes"].add(b["hs"]["value"])
    for b in _sparql(ALIASES_SPARQL, CACHE / "instruments" / "aliases.json", refresh):
        qid = b["item"]["value"].rsplit("/", 1)[1]
        if qid in items:
            items[qid]["aliases"].append(b["alt"]["value"])
    return list(items.values())


def class_names(main: dict[str, dict], lists: dict[str, dict]) -> dict[str, dict]:
    """The merged class table: the lists' names over the main article's, then
    the electrophones and the hand labels, with each name tidied.

    Below the subclasses' first level (three digits) the main article is not
    used at all in a class that has a list, since its deeper numbering is not
    the one Wikidata uses: its 423.233.2 "Irregular bore" would otherwise sit
    under the list's "Cylindrical bore"."""
    main = {d: e for d, e in main.items() if d[0] not in LISTS or len(d) <= 3}
    merged = {**main, **lists}
    for digits, name in ELECTROPHONES.items():
        merged[digits] = {"name": name, "gloss": "", "link": ""}
    out = {}
    for digits, entry in merged.items():
        fallback = main.get(digits, {})
        out[digits] = {**entry, "label": LABELS.get(digits) or tidy(entry["name"]),
                       "gloss": entry["gloss"] or fallback.get("gloss", ""),
                       "link": entry["link"] or fallback.get("link", "")}
    return out


def choose(items: list[dict], classes: dict[str, dict], min_sitelinks: int) -> list[dict]:
    """The instruments to play with, each with the one code it is filed under."""
    def best_code(it: dict) -> tuple[str, str, str]:
        if it["qid"] in CODE_FIXES:
            raw = CODE_FIXES[it["qid"]]
            return (*parse_code(raw), raw)
        parsed = [(parse_code(c), c) for c in sorted(it["codes"])]
        (digits, suffix), raw = max(parsed, key=lambda p: (len(p[0][0]), len(p[0][1])))
        return digits, suffix, raw

    chosen = []
    for it in items:
        if it["sitelinks"] < min_sitelinks or not it["label"] or it["qid"] in EXCLUDE:
            continue
        digits, suffix, raw = best_code(it)
        if len(digits) < 3 or digits[0] not in classes:
            continue
        chosen.append({**it, "digits": digits, "suffix": suffix, "code": raw})
    return chosen


def leaf_names(chosen: list[dict]) -> None:
    """Set each item's `name` (what is shown and guessed) and `alias_list`.

    The label is Wikidata's, except where the English article's title is the
    same word with its diacritics ("gender" is the Balinese gendèr). The title
    and Wikidata's alternative labels become aliases, less any that is another
    instrument's name: the violin's "fiddle" is a fiddle of its own here.
    """
    for it in chosen:
        title = re.sub(r"\s*\(.*\)$", "", title_from_url(it["enwiki"])) if it["enwiki"] else ""
        it["name"] = title if title and fold(title) == fold(it["label"]) and title.casefold() != it["label"].casefold() \
            else it["label"]
    counts: dict[str, int] = {}
    for it in chosen:
        counts[it["name"].casefold()] = counts.get(it["name"].casefold(), 0) + 1
    taken = set(counts)
    for it in chosen:
        if counts[it["name"].casefold()] > 1:
            it["name"] = f"{it['name']} ({it['code']})"
        title = re.sub(r"\s*\(.*\)$", "", title_from_url(it["enwiki"])) if it["enwiki"] else ""
        aliases: list[str] = []
        for a in [title, *sorted(it["aliases"])]:
            a = re.sub(r"\s*\([^()]*\)\s*$", "", a).strip()
            if a and a.casefold() not in taken and a.casefold() not in {x.casefold() for x in aliases}:
                aliases.append(a)
        it["alias_list"] = [*aliases, it["code"]]


def check_labels(tree: dict, classes: dict[str, dict]) -> list[str]:
    """Class nodes whose name will not read out of context."""
    bad = []

    def walk(n: dict) -> None:
        if n.get("children") and n["name"].startswith("hs:") and "-" not in n["name"]:
            label = n.get("label", "")
            if _RELATIVE.match(label) or len(label) > MAX_LABEL:
                digits = n["name"][3:]
                bad.append(f"  {code_text(digits)}: {label!r}  (source: {classes[digits]['name']!r})")
        for c in n.get("children") or []:
            walk(c)
    walk(tree)
    return bad


def build(classes: dict[str, dict], suffixes: dict[str, dict[str, str]],
          items: list[dict], min_sitelinks: int) -> tuple[dict, dict]:
    for cls, table in SUFFIXES.items():
        missing = sorted(set(table) - set(suffixes.get(cls, {})))
        if missing:
            raise SystemExit(f"class {cls} suffixes {missing} are no longer defined at the source")
    chosen = choose(items, classes, min_sitelinks)
    leaf_names(chosen)

    # A leaf hangs from the deepest code that has a name, then from its
    # suffix group where its class's suffixes are used.
    def path_for(it: dict) -> list[str]:
        known = [it["digits"][:k] for k in range(1, len(it["digits"]) + 1) if it["digits"][:k] in classes]
        table = SUFFIXES.get(it["digits"][0], {})
        sfx = [it["suffix"][:k] for k in range(1, len(it["suffix"]) + 1) if it["suffix"][:k] in table]
        return [f"hs:{d}" for d in known] + [f"hs:{known[-1]}-{s}" for s in sfx]

    children: dict[str, list[str]] = {}
    leaves: dict[str, dict] = {}
    for it in sorted(chosen, key=lambda it: (it["digits"], it["suffix"], it["name"].casefold())):
        chain = ["root", *path_for(it), it["qid"]]
        for parent, child in zip(chain, chain[1:]):
            kids = children.setdefault(parent, [])
            if child not in kids:
                kids.append(child)
        leaves[it["qid"]] = node(it["qid"], None, label=it["name"], aliases=it["alias_list"])

    def make(name: str) -> dict:
        if name in leaves:
            return leaves[name]
        kids = [make(c) for c in children.get(name, [])]
        if name == "root":
            return node("root", label="Musical instruments", children=kids)
        base, _, sfx = name[3:].partition("-")
        if sfx:
            return node(name, SUFFIX_RANK[base[0]], label=SUFFIXES[base[0]][sfx], children=kids,
                        aliases=[f"{code_text(base)}-{sfx}"])
        rank = {1: "Class", 2: "Subclass"}.get(len(base))
        return node(name, rank, label=classes[base]["label"], children=kids, aliases=[code_text(base)])

    tree = collapse_lone_children(make("root"), keep={f"hs:{d}" for d in classes if len(d) == 1})
    bad = check_labels(tree, classes)
    if bad:
        raise SystemExit("class names that need an entry in LABELS:\n" + "\n".join(bad))
    return tree, info_for(tree, classes, suffixes, chosen)


def info_for(tree: dict, classes: dict[str, dict], suffixes: dict[str, dict[str, str]],
             chosen: list[dict]) -> dict:
    """Popups: an instrument's English article; a class's linked article where
    the list names one ("Slide trumpets" links its article), else the list's
    own gloss; a suffix group's definition."""
    nodes: list[dict] = []

    def walk(n: dict) -> None:
        nodes.append(n)
        for c in n.get("children") or []:
            walk(c)
    walk(tree)
    kept = [n["name"] for n in nodes]

    titles = {it["qid"]: title_from_url(it["enwiki"]) for it in chosen if it["enwiki"]}
    for name in kept:
        if name.startswith("hs:") and "-" not in name and classes[name[3:]]["link"]:
            titles[name] = classes[name[3:]]["link"]
    got = summaries(sorted(set(titles.values())))

    labels = {n["name"]: n.get("label", n["name"]) for n in nodes}
    info: dict[str, dict] = {}
    for name in kept:
        summary = got.get(titles[name]) if name in titles else None
        if summary and name.startswith("hs:") and not about(labels[name], summary["title"]):
            summary = None
        entry = info_entry(summary)
        if entry:
            info[name] = entry
        elif name.startswith("hs:"):
            base, _, sfx = name[3:].partition("-")
            if base[0] in LISTS:
                source = {"url": f"https://en.wikipedia.org/wiki/{LISTS[base[0]]}",
                          "url_title": f"Hornbostel–Sachs {code_text(base)}{'-' + sfx if sfx else ''} on Wikipedia"}
            else:  # no article numbers the electrophones as Wikidata does; this one discusses them
                source = {"url": f"https://en.wikipedia.org/wiki/{ARTICLE}#Electrophones_(5)",
                          "url_title": "Electrophones in Hornbostel–Sachs, on Wikipedia"}
            if sfx:
                meaning = suffixes[base[0]][sfx]
                text = f"The suffix -{sfx} on a {SUFFIX_NOUN[base[0]]}'s number: {meaning[:1].lower()}{meaning[1:]}."
            else:
                text = classes[base]["gloss"][:1].upper() + classes[base]["gloss"][1:]
            info[name] = {"description": text, **source} if text else source
    return info


def about(label: str, title: str) -> bool:
    """Whether an article a class links to is about that class. Links are
    followed through redirects, and some land wide: "tubular drums" on
    *Membranophone*, "flutes" on a list of every instrument there is. Those
    would answer for the wrong node, so an article must share a word with the
    class's name."""
    def stems(s: str) -> set[str]:
        return {w[:5] for w in re.findall(r"[a-z]{4,}", fold(s))}
    return not title.startswith("List of") and bool(stems(label) & stems(title))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-sitelinks", type=int, default=MIN_SITELINKS)
    ap.add_argument("--refresh", action="store_true", help="fetch the articles and query Wikidata again")
    args = ap.parse_args()

    def article(page: str, cache_name: str) -> str:
        return fetch(WIKI + page, CACHE / "instruments" / cache_name, refresh=args.refresh).read_text()

    main_classes = parse_classes(article(ARTICLE, "hornbostel-sachs.wiki"))
    texts = {cls: article(page, f"list-{cls}.wiki") for cls, page in LISTS.items()}
    lists: dict[str, dict] = {}
    for cls, text in texts.items():
        lists.update(parse_classes(text, only=cls))
    suffixes = {cls: parse_suffixes(texts[cls]) for cls in SUFFIXES}
    tree, info = build(class_names(main_classes, lists), suffixes, wikidata(args.refresh), args.min_sitelinks)
    write_dataset("instruments", tree, info)


if __name__ == "__main__":
    main()
