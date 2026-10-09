"""Build `datasets/chess`: named chess openings, on the tree of their moves.

The other trees here are classifications somebody drew. This one is not drawn
by anyone: an opening *is* a sequence of moves, so two openings are related
exactly as far as their moves agree, and their lowest common ancestor is the
last move they share. The Najdorf and the Dragon part at Black's fifth move;
the Najdorf and the French part at Black's first. Nothing has to be judged.

**Source.** The Lichess opening list (CC0), pinned at `REF`: 3,865 lines under
3,177 names in the shape `Family: Variation, Subvariation, …`, each with its
ECO code and the line in standard notation.

**Which openings.** All 3,177 would make a round unwinnable, since a secret is
drawn uniformly and most names are deep theory nobody has heard of. Kept:

* every family (`Sicilian Defense`, `Bongcloud Attack`);
* every variation (`Sicilian Defense: Najdorf Variation`) that has at least
  `MIN_NAMES` names under it in the full list, its own included. A variation
  people have named sublines of is one people play;
* `ALSO`, a short hand list of famous sublines the rule misses, such as the
  Fried Liver Attack and the Sveshnikov. The build fails if Lichess renames one.

Names whose *family* part has a comma are left out: they are Lichess's
transposition markers (`London System, with Bd3`), not openings.

**Shape.** Positions are internal nodes, named by their line
(`1. e4 c5 2. Nf3`), and each opening is a leaf hanging from the position it
names, so `Sicilian Defense` sits beside the moves that continue from it. A
position with one way on is merged into it — its label grows to
`…e6 2.d4 d5` — and a position whose only content is its own opening becomes
that opening. Depth therefore counts branch points, not moves: a node's warmth
says how many of the choices that lead to the answer you have matched, and the
manifest has no ladder.

**Popups.** Every node gets its board, drawn here as a small SVG data URL
(`board_svg`), with the last move marked. An opening also gets its line as a
subtitle and, where English Wikipedia has an article about it, that article's
lead (`wiki_for`). Titles are guessed, so a guess is believed only when the
article is about chess, names the opening's own distinctive word, gives moves
that agree with the opening's, and is not the article of an opening above it:
"Sicilian Defence, Kan Variation" redirects to *Sicilian Defence*, which is not
about the Kan. The text is the whole lead (`wikipedia.intros`), since the
summary endpoint stops at the move list a chess lead opens with.

The board is drawn with the chess glyphs of the reader's system fonts, which
every current desktop and phone carries. Moves are replayed by `san.py`.
"""
from __future__ import annotations

import argparse
import csv
import re
import urllib.parse
from collections import Counter

from common import CACHE, fetch, node, write_dataset
from san import Position, moves_of, play
from wikipedia import info_entry, intros, summaries

REF = "a6189a30dc273ccb21fc2536a9a2fefd5592a67a"   # lichess-org/chess-openings, 2026-10-06
TSV = "https://raw.githubusercontent.com/lichess-org/chess-openings/{ref}/{vol}.tsv"
VOLUMES = "abcde"
MIN_NAMES = 2

ALSO = [
    "Italian Game: Jerome Gambit",
    "Italian Game: Two Knights Defense, Fried Liver Attack",
    "Italian Game: Two Knights Defense, Traxler Counterattack",
    "Sicilian Defense: Smith-Morra Gambit",
    "Sicilian Defense: Lasker-Pelikan Variation, Sveshnikov Variation",
    "Sicilian Defense: Dragon Variation, Yugoslav Attack",
    "Sicilian Defense: Najdorf Variation, English Attack",
    "Sicilian Defense: Najdorf Variation, Poisoned Pawn Variation",
    "Sicilian Defense: Accelerated Dragon, Maróczy Bind",
    "Ruy Lopez: Closed, Breyer Defense",
    "Ruy Lopez: Closed, Chigorin Defense",
    "Ruy Lopez: Closed, Zaitsev System",
    "Ruy Lopez: Berlin Defense, l'Hermet Variation, Berlin Wall Defense",
    "Ruy Lopez: Berlin Defense, Fishing Pole Variation",
    "Petrov's Defense: Stafford Gambit",
    "Queen's Gambit Declined: Albin Countergambit, Lasker Trap",
    "Scandinavian Defense: Mieses-Kotroc Variation",
    "Vienna Game: Frankenstein-Dracula Variation",
    "Nimzo-Indian Defense: Rubinstein System, Hübner Variation",
    "French Defense: Winawer Variation, Poisoned Pawn Variation",
    "Indian Defense: Budapest Gambit",
]

# What else a player might type. British spellings are added for every name
# (`aliases_for`); these are the other names an opening goes by.
ALIASES = {
    "Ruy Lopez": ["Spanish Game", "Spanish Opening"],
    "Petrov's Defense": ["Russian Game", "Petroff Defence"],
    "Italian Game: Giuoco Piano": ["Giuoco Piano"],
    "Italian Game: Two Knights Defense": ["Two Knights Defence"],
    "Indian Defense: Budapest Gambit": ["Budapest Gambit"],
    "Polish Opening": ["Sokolsky Opening", "Orangutan"],
    "Nimzo-Larsen Attack": ["Larsen's Opening"],
    "Grob Opening": ["Grob's Attack"],
    "Zukertort Opening": ["1.Nf3"],
}

# Words that say what kind of line a name is, and so cannot tell one article
# from another.
GENERIC = {
    "variation", "defense", "defence", "attack", "gambit", "system", "line", "opening", "game",
    "accepted", "declined", "countergambit", "counterattack", "the", "main", "with",
}


def load_lines(refresh: bool) -> list[dict]:
    rows = []
    for vol in VOLUMES:
        path = fetch(TSV.format(ref=REF, vol=vol), CACHE / "chess" / f"{vol}.tsv", refresh=refresh)
        with open(path, newline="") as f:
            rows += list(csv.DictReader(f, delimiter="\t"))
    return rows


def parts(name: str) -> tuple[str, list[str]]:
    """'Sicilian Defense: Najdorf Variation, English Attack' ->
    ('Sicilian Defense', ['Najdorf Variation', 'English Attack'])."""
    family, _, rest = name.partition(":")
    return family.strip(), [v.strip() for v in rest.split(",")] if rest else []


def ancestors(name: str) -> list[str]:
    """The names above this one in Lichess's naming, broadest first."""
    family, variations = parts(name)
    out = [family]
    for i in range(1, len(variations)):
        out.append(f"{family}: {', '.join(variations[:i])}")
    return out if variations else []


def shortest_lines(rows: list[dict]) -> dict[str, dict]:
    """Each name's shortest line; Lichess lists transpositions as extra rows
    under the same name, and guarantees the shortest is unique."""
    best: dict[str, dict] = {}
    for r in rows:
        moves = moves_of(r["pgn"])
        if r["name"] not in best or len(moves) < len(best[r["name"]]["moves"]):
            best[r["name"]] = {"name": r["name"], "eco": r["eco"], "moves": moves}
    return best


def select(best: dict[str, dict]) -> list[dict]:
    under = Counter()
    for name in best:
        family, variations = parts(name)
        if variations:
            under[(family, variations[0])] += 1
    kept = []
    for name, line in best.items():
        family, variations = parts(name)
        if "," in family:
            continue
        if not variations or (len(variations) == 1 and under[(family, variations[0])] >= MIN_NAMES):
            kept.append(line)
    missing = [n for n in ALSO if n not in best]
    if missing:
        raise SystemExit(f"ALSO names Lichess no longer has: {missing}")
    have = {line["name"] for line in kept}
    kept += [best[n] for n in ALSO if n not in have]
    return kept


def pgn(moves: list[str]) -> str:
    """['e4', 'c5', 'Nf3'] -> '1. e4 c5 2. Nf3', the form Lichess writes."""
    out = []
    for i, m in enumerate(moves):
        out.append(f"{i // 2 + 1}. {m}" if i % 2 == 0 else m)
    return " ".join(out)


def segment(moves: list[str], start: int) -> str:
    """The moves from ply `start` on, compactly: '…e6 2.d4 d5'. A segment that
    opens on Black's move says so with the move number and an ellipsis."""
    out = []
    for i in range(start, len(moves)):
        n = i // 2 + 1
        if i % 2 == 0:
            out.append(f"{n}.{moves[i]}")
        else:
            out.append(f"{n}…{moves[i]}" if i == start else moves[i])
    return " ".join(out)


class Trie:
    def __init__(self, moves: tuple[str, ...] = ()) -> None:
        self.moves = moves
        self.next: dict[str, Trie] = {}
        self.openings: list[dict] = []

    def add(self, line: dict) -> None:
        at = self
        for m in line["moves"]:
            at = at.next.setdefault(m, Trie(at.moves + (m,)))
        at.openings.append(line)

    def leaves(self) -> int:
        return len(self.openings) + sum(c.leaves() for c in self.next.values())


def aliases_for(name: str) -> list[str]:
    out = list(ALIASES.get(name, []))
    british = name.replace("Defense", "Defence")
    if british != name:
        out.append(british)
    return out


def build(lines: list[dict]) -> dict:
    root = Trie()
    for line in lines:
        root.add(line)

    def leaf(line: dict) -> dict:
        return node(line["name"], rank=line["eco"], aliases=aliases_for(line["name"]) or None)

    def convert(at: Trie, start: int, is_root: bool = False) -> dict:
        # A position with one way on and nothing named is merged into the next.
        while not is_root and not at.openings and len(at.next) == 1:
            at = next(iter(at.next.values()))
        kids = [leaf(o) for o in sorted(at.openings, key=lambda o: o["name"])]
        onward = sorted(at.next.items(), key=lambda kv: (-kv[1].leaves(), kv[0]))
        kids += [convert(child, len(at.moves)) for _, child in onward]
        if not is_root and len(kids) == 1 and not kids[0].get("children"):
            return kids[0]
        moves = list(at.moves)
        if is_root:
            return node("Starting position", label="Start", rank="Position", children=kids)
        return node(pgn(moves), label=segment(moves, start), rank="Position", children=kids)

    return convert(root, 0, is_root=True)


# --- boards -----------------------------------------------------------------

GLYPHS = dict(zip("kqrbnp", "♚♛♜♝♞♟"))
LIGHT, DARK, MARK = "#ecdab9", "#ae8a68", "#cdd26a"


def board_svg(pos: Position) -> str:
    """The position as a compact SVG, white at the bottom.

    One `<text>` per side, with a position per glyph, keeps a board under a
    kilobyte. White pieces are the solid glyphs filled white and outlined,
    which reads as white on either square colour. Apple Symbols leads the font
    list so Safari draws the pawn as a glyph rather than as an emoji.
    """
    out = [
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 80 80' "
        "font-family='Apple Symbols,Segoe UI Symbol,DejaVu Sans,Noto Sans Symbols 2' "
        "font-size='8.6' text-anchor='middle'>",
        "<pattern id='c' width='20' height='20' patternUnits='userSpaceOnUse'>"
        f"<path d='M10 0h10v10H10zM0 10h10v10H0z' fill='{DARK}'/></pattern>",
        f"<rect width='80' height='80' fill='{LIGHT}'/><rect width='80' height='80' fill='url(#c)'/>",
    ]
    if pos.last:
        marks = "".join(f"M{f * 10} {70 - r * 10}h10v10h-10z" for f, r in pos.last)
        out.append(f"<path d='{marks}' fill='{MARK}' opacity='.6'/>")
    for white, paint in ((False, ""), (True, " fill='#fff' stroke='#000' stroke-width='.35'")):
        pieces = sorted((sq, p) for sq, p in pos.board.items() if p.isupper() == white)
        xs = " ".join(str(f * 10 + 5) for (f, _), _ in pieces)
        ys = " ".join(str(78 - r * 10) for (_, r), _ in pieces)
        glyphs = "".join(GLYPHS[p.lower()] for _, p in pieces)
        out.append(f"<text x='{xs}' y='{ys}'{paint}>{glyphs}</text>")
    out.append("</svg>")
    return "".join(out)


def data_url(svg: str) -> str:
    """A data URL that every browser reads: `#` and `%` must be escaped, and
    non-ASCII is percent-encoded rather than trusted to the URL parser."""
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg, safe=" '=:/;,.-<>()")


# --- Wikipedia --------------------------------------------------------------

def _fold(s: str) -> str:
    return re.sub(r"[‐-―-]", " ", s.lower().replace("defence", "defense")).replace("'s", "")


def distinctive(part: str) -> str:
    """The first word of a name part that says which line it is: 'Najdorf' of
    'Najdorf Variation', 'Two' of 'Two Knights Defense'."""
    for word in _fold(part).split():
        if word not in GENERIC:
            return word
    return ""


def candidates(name: str) -> list[str]:
    """Titles to try, most specific first. Never the title of an opening
    above this one: "Ruy Lopez, Berlin Defence" is the Berlin's article, not
    the Berlin Wall's."""
    family, variations = parts(name)
    british = [p.replace("Defense", "Defence") for p in [family, *variations]]
    if not variations:
        return [british[0]]
    out = [", ".join(british)]
    if len(variations) > 1:
        out.append(f"{british[0]}, {british[-1]}")
    return out + [british[-1]]


# Set-index articles: "The Taimanov Variation can refer to variations of four
# different chess openings". About the name, not the opening.
SET_INDEX = re.compile(r"\b(?:may|can) refer to|applied to several|any of several|"
                       r"given to a few|a number of chess openings", re.I)
_MOVE = re.compile(r"^(?:[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=?[NBRQ])?|O-O(?:-O)?)[+#!?]*$")


def article_line(text: str) -> list[str]:
    """The moves an article's lead gives for its opening — 'begins with the
    moves: 1. e4 e5 2. Nf3' — or [] when it names none."""
    at = re.search(r"\b1\.\s*(?=[a-hNBRQK0O])", text)
    if not at:
        return []
    moves = []
    for token in text[at.start():].replace("0-0", "O-O").split():
        token = re.sub(r"^\d+\.+", "", token).rstrip(",;:)")
        if not token:
            continue
        if not _MOVE.match(token):
            break
        moves.append(token.rstrip("+#!?"))
    return moves


def wiki_for(names: list[str], lines: dict[str, list[str]]) -> dict[str, dict]:
    """Opening name to its Wikipedia summary, for those that have an article.

    `lines` holds the moves of every Lichess name, since the openings above a
    kept one are looked up too, to be ruled out."""
    wanted = {n: candidates(n) for n in names}
    for a in {a for n in names for a in ancestors(n)}:
        wanted.setdefault(a, candidates(a))
    found = summaries(sorted({c for cs in wanted.values() for c in cs}))

    def first_fit(name: str) -> dict | None:
        family, variations = parts(name)
        own = distinctive(variations[-1] if variations else family)
        ours = lines.get(name, [])
        bare = candidates(name)[-1] if variations else None
        for title in wanted[name]:
            s = found.get(title)
            if not s or SET_INDEX.search(s["description"]):
                continue
            theirs = article_line(s["description"])
            if "chess" not in s["description"].lower() and not theirs:
                continue
            # Named for this opening: "Advance Variation" redirects to the
            # French Defence, which is no use to the Caro-Kann's.
            if own and own not in _fold(s["title"]):
                continue
            # And about these moves, where it gives any: a "Four Knights
            # Variation" that lands on the Four Knights Game is 1.e4 e5, not
            # the Sicilian's 1.e4 c5.
            n = min(len(ours), len(theirs))
            if ours and n and ours[:n] != theirs[:n]:
                continue
            # A bare variation name is a weak guess — it finds Mikhail Chigorin
            # for the Chigorin Variation. It needs the article's moves to
            # agree, or an opening's kind of title and the family named.
            if title == bare and not n:
                kind = set(_fold(s["title"]).split()) & (GENERIC | {"bind", "trap"})
                if not kind or distinctive(family) not in _fold(s["description"]):
                    continue
            return s
        return None

    fits = {n: first_fit(n) for n in wanted}
    out = {}
    for n in names:
        s = fits[n]
        # A redirect to a section lands on the article above: "Meran Variation"
        # is the Semi-Slav's article, which the Semi-Slav already has.
        if s and all(not fits.get(a) or fits[a]["title"] != s["title"] for a in ancestors(n)):
            out[n] = s

    # Where several openings land on one article, it belongs to the one it is
    # named for: the King's Gambit's, not the King's Gambit Accepted's.
    def key(text: str) -> str:
        return _fold(text.split(", ")[-1].split(": ")[-1]).strip()

    by_title: dict[str, list[str]] = {}
    for n, s in out.items():
        by_title.setdefault(s["title"], []).append(n)
    for title, ns in by_title.items():
        named = [n for n in ns if key(n) == key(title)]
        for n in ns:
            if named and n not in named:
                del out[n]
    return out


_MOVE_LINE = re.compile(r"^\d+\.\s*\S+(?:\s+\S+)?$")


def tidy_intro(text: str) -> str:
    """An article's lead as popup text. The move list it opens with is set as
    lines of its own ("1. e4 c5", "2. Nf3 d6"); joined back into the sentence
    that introduces it, with the sentence after, so the first paragraph — all
    the popup shows before "Show more" — says more than the subtitle does."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    out: list[str] = []
    i = 0
    while i < len(lines):
        if out and _MOVE_LINE.match(lines[i]):
            moves = []
            while i < len(lines) and _MOVE_LINE.match(lines[i]):
                moves.append(lines[i])
                i += 1
            joined = " ".join(moves).replace("0-0-0", "O-O-O").replace("0-0", "O-O")
            after = lines[i] if i < len(lines) else ""
            i += 1 if after else 0
            out.append(f"{out.pop().rstrip(':').rstrip()} {joined}." + (f" {after}" if after else ""))
        else:
            out.append(lines[i])
            i += 1
    # What is left of a pronunciation the plain text could not carry: "( NY-dorf)".
    return re.sub(r"\(\s*\)", "", re.sub(r"\(\s+", "(", "\n".join(out)))


def info_for(tree: dict, lines: dict[str, dict], every: dict[str, dict]) -> dict[str, dict]:
    wiki = wiki_for(list(lines), {n: line["moves"] for n, line in every.items()})
    leads = intros(sorted({s["title"] for s in wiki.values()}))
    wiki = {n: {**s, "description": tidy_intro(leads[s["title"]])} if leads.get(s["title"]) else s
            for n, s in wiki.items()}
    info: dict[str, dict] = {}

    def walk(n: dict) -> None:
        if n.get("children"):
            moves = [] if n["name"] == "Starting position" else moves_of(n["name"])
            info[n["name"]] = {"image_url": data_url(board_svg(play(moves)))}
            for c in n["children"]:
                walk(c)
            return
        line = lines[n["name"]]
        entry = info_entry(wiki.get(n["name"])) or {}
        entry.pop("image_url", None)   # the board says more than a portrait of Najdorf
        info[n["name"]] = {**entry, "subtitle": pgn(line["moves"]),
                           "image_url": data_url(board_svg(play(line["moves"])))}

    walk(tree)
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="download the Lichess list again")
    args = ap.parse_args()

    best = shortest_lines(load_lines(args.refresh))
    kept = select(best)
    tree = build(kept)
    info = info_for(tree, {line["name"]: line for line in kept}, best)
    print(f"{len(kept)} openings of {len(best)} names; "
          f"{sum(1 for v in info.values() if 'description' in v)} with Wikipedia text")
    write_dataset("chess", tree, info)


if __name__ == "__main__":
    main()
