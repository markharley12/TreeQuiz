#!/usr/bin/env python3
"""datasets/maths — fields of mathematics, from the Mathematics Subject
Classification (MSC2020).

MSC2020 is a three-level tree: 63 two-digit **subjects** (`35-XX` Partial
differential equations), ~530 **sections** under them (`35Jxx` Elliptic
equations), and ~5,500 five-character **topics** under those (`35J05`
Laplace and Poisson equations). It is maintained by zbMATH Open and
Mathematical Reviews and published at https://msc2020.org under CC BY-NC-SA 4.0.

**The leaves are the sections.** A topic is too fine to guess by name ("Curves
of arbitrary genus or genus ≠ 1 over global fields"), and a subject too coarse
(63 leaves). The topics are kept as each section's popup text, so they are
still there to read.

**A curated layer sits above the subjects**, because MSC itself has none. That
is TaxoQuiz's flat-example bug in another domain: with 63 subjects directly
under the root, guessing a wrong subject says nothing at all, and number theory
is exactly as far from algebraic geometry as from fluid mechanics. `BRANCHES`
below groups them into five branches and, where a branch is big, areas within
it. **This grouping is ours, not MSC's** — MSC's numbering is roughly ordered
this way (algebra in the teens, analysis in the 20s–40s, geometry in the 50s,
applied from 60), which is what it follows, but the boundaries are judgement
calls and the table is the place to argue with them. Two rules from TaxoQuiz's
clade layer: only groups that actually branch (a one-subject area would be a
pass-through, never anyone's LCA), and an unranked group where a level is
wanted that the ladder does not have — Mechanics, inside Mathematical physics.

Left out: `00` (general and overarching topics), `01` (history and biography)
and `97` (mathematics education), which classify writing *about* mathematics
rather than fields of it; the `NN-0x` form classes (textbooks, proceedings...);
and every `99` topic, "None of the above, but in this section".

**Labels.** A section's MSC text is often only meaningful inside its subject —
`20Axx` is "Foundations", `16Bxx` "General and miscellaneous" — and a leaf is
guessed by its label alone, so those (listed in `QUALIFY`) get their subject in
parentheses: "Foundations (group theory)". A subject with a single section is
one leaf, named for the subject. TeX is rendered to plain Unicode.

Usage:
    python3 datagen/build_maths.py [--refresh]
"""
from __future__ import annotations

import argparse
import csv
import re

from common import CACHE, fetch, node, write_dataset

SOURCE = "https://msc2020.org/MSC_2020.csv"

# The layer above the subjects — ours, not MSC's; see the docstring. A string
# is a subject directly under its branch; a tuple is (area, [members]), and an
# area whose label starts with "~" is unranked.
BRANCHES: list[tuple[str, list]] = [
    ("Logic and discrete mathematics", ["03", "05", "06"]),
    ("Algebra and number theory", [
        "11", "14",
        ("Rings, fields and algebras", ["08", "12", "13", "15", "16", "17"]),
        ("Groups", ["20", "22"]),
        ("Categories and K-theory", ["18", "19"]),
    ]),
    ("Analysis", [
        ("Real and complex analysis", ["26", "28", "30", "31", "32", "33"]),
        ("Differential and integral equations", ["34", "35", "37", "39", "45"]),
        ("Series, approximations and transforms", ["40", "41", "44"]),
        ("Harmonic and functional analysis", ["42", "43", "46", "47"]),
        "49",
    ]),
    ("Geometry and topology", [
        ("Geometries", ["51", "52", "53"]),
        ("Topology", ["54", "55", "57"]),
        "58",
    ]),
    ("Applied mathematics", [
        ("Probability and statistics", ["60", "62"]),
        ("Computation and information", ["65", "68", "94"]),
        ("Mathematical physics", [
            ("~Mechanics", ["70", "74", "76"]),
            "78", "80", "81", "82", "83", "85", "86",
        ]),
        ("Operations research and control", ["90", "93"]),
        ("Social and life sciences", ["91", "92"]),
    ]),
]
EXCLUDED_SUBJECTS = {"00", "01", "97"}

# How a subject is named inside a qualified section label.
SHORT = {
    "03": "logic", "05": "combinatorics", "06": "order theory", "08": "universal algebra",
    "11": "number theory", "12": "field theory", "13": "commutative algebra",
    "14": "algebraic geometry", "15": "linear algebra", "16": "associative rings",
    "17": "nonassociative rings", "18": "category theory", "19": "K-theory",
    "20": "group theory", "22": "topological groups", "26": "real functions",
    "28": "measure theory", "30": "complex analysis", "31": "potential theory",
    "32": "several complex variables", "33": "special functions", "34": "ODEs",
    "35": "PDEs", "37": "dynamical systems", "39": "difference equations",
    "40": "summability", "41": "approximation theory", "42": "harmonic analysis",
    "43": "abstract harmonic analysis", "44": "integral transforms",
    "45": "integral equations", "46": "functional analysis", "47": "operator theory",
    "49": "calculus of variations", "51": "geometry", "52": "convex geometry",
    "53": "differential geometry", "54": "general topology", "55": "algebraic topology",
    "57": "manifolds", "58": "global analysis", "60": "probability", "62": "statistics",
    "65": "numerical analysis", "68": "computer science", "70": "particle mechanics",
    "74": "solid mechanics", "76": "fluid mechanics", "78": "optics", "80": "thermodynamics",
    "81": "quantum theory", "82": "statistical mechanics", "83": "relativity",
    "85": "astronomy", "86": "geophysics", "90": "operations research",
    "91": "economics and social sciences", "92": "biology", "93": "systems theory",
    "94": "information theory",
}

# Sections whose MSC text needs its subject to stand alone as a guess. Chosen by
# reading all ~530; any label that collides is qualified as well, whatever this
# list says.
QUALIFY = {
    "08Axx", "08Bxx", "08Cxx", "11Bxx", "11Cxx", "11Exx", "16Bxx", "16Uxx", "16Yxx",
    "20Axx", "26Axx", "26Bxx", "40Exx", "49Qxx", "60Axx", "60Exx", "70Axx",
}

BLACKBOARD = dict(zip("ABCDEFGHNPQRZ", "𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍℕℙℚℝℤ"))
SYMBOLS = {
    "infty": "∞", "partial": "∂", "ge": "≥", "geq": "≥", "le": "≤", "leq": "≤",
    "ne": "≠", "subset": "⊂", "dots": "…", "ldots": "…", "cdot": "·", "times": "×",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "varepsilon": "ε",
    "epsilon": "ε", "zeta": "ζ", "eta": "η", "theta": "θ", "lambda": "λ", "mu": "μ",
    "pi": "π", "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ", "psi": "ψ",
    "omega": "ω", "Gamma": "Γ", "Delta": "Δ", "Lambda": "Λ", "Pi": "Π", "Sigma": "Σ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
SUB = dict(zip("0123456789+-=()aehijklmnoprstuvx", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))
SUP = dict(zip("0123456789+-=()cinkt*", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ᶜⁱⁿᵏᵗ*"))


def _script(text: str, table: dict[str, str], mark: str) -> str:
    if all(c in table for c in text):
        return "".join(table[c] for c in text)
    return f"{mark}{text}" if len(text) == 1 else f"{mark}({text})"


def detex(s: str) -> str:
    """MSC's inline TeX to plain Unicode. Covers what MSC2020 uses, not TeX."""
    def math(m: re.Match) -> str:
        t = m.group(1)
        t = re.sub(r"\\mathbb\{(\w)\}", lambda b: BLACKBOARD.get(b.group(1), b.group(1)), t)
        t = re.sub(r"\\overline\{(\w+)\}", lambda b: b.group(1) + "\u0305", t)
        t = re.sub(r"\\(?:mathrm|mbox|mathcal|text|operatorname)\{([^}]*)\}", r"\1", t)
        t = re.sub(r"\\([A-Za-z]+)", lambda b: SYMBOLS.get(b.group(1), b.group(1)), t)
        t = re.sub(r"_\{([^}]*)\}|_(\w)", lambda b: _script(b.group(1) or b.group(2), SUB, "_"), t)
        t = re.sub(r"\^\{([^}]*)\}|\^(\S)", lambda b: _script(b.group(1) or b.group(2), SUP, "^"), t)
        return t.replace("{}", "").replace("\\,", " ")
    s = re.sub(r"\\\((.*?)\\\)", math, s)
    s = s.replace("\\{", "{").replace("\\}", "}")
    return re.sub(r"\s+", " ", s).strip()


def read_msc(path) -> dict[str, dict]:
    with open(path, encoding="latin-1", newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    return {r["code"].strip(): {"text": detex(r["text"]), "description": detex(r["description"])} for r in rows}


def notes_of(entry: dict) -> str:
    """What a description says beyond the label: MSC's cross-references."""
    text, desc = entry["text"], entry["description"]
    extra = desc[len(text):].strip() if desc.startswith(text) else desc if desc != text else ""
    # "{For x, see 58J10}" and "[See also 03A05]" are MSC's notation for notes;
    # as sentences they read better without it.
    notes = [m.strip() for m in re.findall(r"[{\[]([^{}\[\]]*)[}\]]?", extra) if m.strip()]
    return " ".join(n if n.endswith(".") else n + "." for n in notes) if notes else extra


def zbmath(code: str) -> dict:
    return {"url": f"https://zbmath.org/classification/?q=cc:{code}", "url_title": f"MSC {code} on zbMATH Open"}


def build(msc: dict[str, dict]) -> tuple[dict, dict]:
    subjects = {c[:2]: e for c, e in msc.items() if re.fullmatch(r"\d\d-XX", c)}
    sections: dict[str, list[str]] = {}
    for c in msc:
        if re.fullmatch(r"\d\d[A-Z]xx", c):
            sections.setdefault(c[:2], []).append(c)
    topics: dict[str, list[str]] = {}
    for c in msc:
        if re.fullmatch(r"\d\d[A-Z]\d\d", c) and not c.endswith("99"):
            topics.setdefault(c[:3], []).append(c)

    placed = [s for _, members in BRANCHES for s in _subjects_in(members)]
    missing = set(subjects) - set(placed) - EXCLUDED_SUBJECTS
    if missing or len(placed) != len(set(placed)):
        raise SystemExit(f"BRANCHES must place every subject once; missing {sorted(missing)}")

    # Labels a leaf would collide on are qualified too, whatever QUALIFY says.
    leaf_texts: dict[str, int] = {}
    for subj in placed:
        for sec in sections.get(subj, []):
            leaf_texts[msc[sec]["text"].lower()] = leaf_texts.get(msc[sec]["text"].lower(), 0) + 1

    info: dict[str, dict] = {}

    def section_node(code: str) -> dict:
        e = msc[code]
        label = e["text"]
        if code in QUALIFY or leaf_texts[label.lower()] > 1:
            label = f"{label} ({SHORT[code[:2]]})"
        info[code] = {
            "description": notes_of(e),
            "items": [msc[t]["text"] for t in topics.get(code[:3], [])],
            **zbmath(code[:3]),
        }
        return node(code, "Section", label=label, aliases=[code[:3]])

    def subject_node(subj: str) -> dict:
        code, e = f"{subj}-XX", subjects[subj]
        secs = sections[subj]
        if len(secs) == 1:
            # One section is the subject: a single leaf, named for the subject.
            only = secs[0]
            info[only] = {
                "description": notes_of(e) or notes_of(msc[only]),
                "items": [msc[t]["text"] for t in topics.get(only[:3], [])],
                **zbmath(subj),
            }
            return node(only, "Subject", label=e["text"], aliases=[subj, only[:3]])
        info[code] = {"description": notes_of(e), "items": [msc[s]["text"] for s in secs], **zbmath(subj)}
        return node(code, "Subject", label=e["text"], aliases=[subj], children=[section_node(s) for s in secs])

    def member(m) -> dict:
        if isinstance(m, str):
            return subject_node(m)
        label, members = m
        unranked = label.startswith("~")
        label = label.lstrip("~")
        return node(label, None if unranked else "Area", children=[member(x) for x in members])

    tree = node("Mathematics", "Mathematics", children=[
        node(label, "Branch", children=[member(m) for m in members]) for label, members in BRANCHES
    ])
    return tree, info


def _subjects_in(members: list) -> list[str]:
    out = []
    for m in members:
        out += [m] if isinstance(m, str) else _subjects_in(m[1])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="download the CSV again")
    args = ap.parse_args()
    tree, info = build(read_msc(fetch(SOURCE, CACHE / "MSC_2020.csv", refresh=args.refresh)))
    write_dataset("maths", tree, info)


if __name__ == "__main__":
    main()
