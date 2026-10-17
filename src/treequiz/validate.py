"""Is this tree fit to play on? TaxoQuiz's `validate_dataset.py`, generalised.

Every other test checks code against a fixture it wrote, which is why both of
TaxoQuiz's data bugs got past its suite: code that correctly colours a tree it
is handed cannot say the tree is wrong. This checks the *shipped* tree, against
the engine's assumptions and against something outside itself.

Three groups, weakest first; each catches what the one before cannot:

1. **Shape** — what the engine assumes. Unique names (indexes key on them, so a
   duplicate corrupts play without raising), leaf labels unique ignoring case
   (a leaf is guessed by its label, and the app capitalises on display, so two
   that differ only in case are one choice to a player), no empty `children`.
2. **Warmth** — going deeper is strictly warmer, and the share of rank claims
   the ladder had to reject. Above 5% the ranks are rotten upstream.
3. **Orderings** — the manifest's `checks.closer`: relationships nobody
   disputes, asserted as an *ordering* of LCA warmth rather than as numbers,
   so they survive a rebuild. `{"to": "Homo sapiens", "order": ["Pan
   troglodytes", "Panthera leo", ...]}` says a human is closer to a chimp than
   to a lion, and so on down. Names absent from the tree are skipped, not failed.
   This is the group that catches a tree which is internally consistent and
   still wrong — TaxoQuiz's flat Animalia → Phylum example was exactly that.

A sized tree (see size.py) is also checked at every stop: its `sizes` make
sense, every leaf has a `fame`, and warmth rises and the orderings hold on
each cut, since a cut moves warmth wherever it is placed by shape.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field

from .dataset import Dataset
from .ladder import rejected_share, warmth_by_name
from .size import Sizes
from .tree import all_nodes, children_of, label_of, leaves

MAX_REJECTED_SHARE = 0.05


@dataclass
class Report:
    name: str
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.failures

    def render(self) -> str:
        lines = [self.name, "-" * len(self.name)]
        lines += [f"  note: {n}" for n in self.notes]
        lines += [f"  FAIL: {f}" for f in self.failures]
        lines.append(f"  => {'OK' if self.ok else f'{len(self.failures)} FAILURES'}")
        return "\n".join(lines)


def _edges(node: dict, parent: dict | None = None):
    yield node, parent
    for child in children_of(node):
        yield from _edges(child, node)


def check_shape(ds: Dataset, r: Report) -> None:
    tree = ds.tree
    if not ds.manifest.get("title"):
        r.fail("manifest has no title")
    names: collections.Counter[str] = collections.Counter()
    for node, parent in _edges(tree):
        name = node.get("name")
        if not isinstance(name, str) or not name:
            r.fail(f"a node under {parent and parent.get('name')!r} has no name")
            continue
        names[name] += 1
        if node.get("children") is not None and not node["children"]:
            r.fail(f"{name!r} has an empty children list; a leaf must omit it")
        if "label" in node and (not isinstance(node["label"], str) or not node["label"].strip()):
            r.fail(f"{name!r} has a blank label")
        fame = node.get("fame")
        if fame is not None and (not isinstance(fame, int) or isinstance(fame, bool) or fame < 0):
            r.fail(f"{name!r} has a fame that is not a non-negative integer: {fame!r}")
        elif fame is not None and children_of(node):
            r.fail(f"{name!r} has a fame but is not a leaf; only leaves are ranked")
        aliases = node.get("aliases")
        if aliases is not None and (not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases)):
            r.fail(f"{name!r} has aliases that are not a list of strings")
    dupes = sorted(n for n, c in names.items() if c > 1)
    if dupes:
        r.fail(f"{len(dupes)} duplicate node names, e.g. {dupes[:3]}")

    lv = leaves(tree)
    if len(lv) < 2:
        r.fail(f"only {len(lv)} leaf; a game needs at least two")
    labels = collections.Counter(label_of(n).lower() for n in lv)
    clash = sorted(n for n, c in labels.items() if c > 1)
    if clash:
        r.fail(f"{len(clash)} leaf labels collide ignoring case, e.g. {clash[:3]}")
    if "???" in labels:
        r.fail("a leaf is labelled '???', which is what the secret marker says")

    internal = [n for n in all_nodes(tree) if children_of(n)]
    chains = sum(1 for n in internal if len(children_of(n)) == 1)
    depth = max(len(_path) for _path in _lineages(tree).values()) - 1
    r.note(f"{len(lv)} leaves, {len(internal)} internal nodes, max depth {depth}, "
           f"{chains} single-child nodes")


def _lineages(tree: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}

    def walk(node: dict, path: list[str]) -> None:
        path = path + [node["name"]]
        if not children_of(node):
            out[node["name"]] = path
        for c in children_of(node):
            walk(c, path)

    walk(tree, [])
    return out


def check_warmth(ds: Dataset, r: Report) -> None:
    check_edges(ds, r)
    rejected, ranked = rejected_share(ds.tree, ds.ladder)
    if ranked:
        share = rejected / ranked
        line = f"rank claims rejected by the tree: {rejected} of {ranked} ({100 * share:.2f}%)"
        (r.fail if share > MAX_REJECTED_SHARE else r.note)(line)
    elif ds.manifest.get("ladder"):
        r.fail("the manifest has a ladder but no internal node has a rank on it")
    else:
        r.note("no ladder: every internal node is placed by the tree's shape")


def check_edges(ds: Dataset, r: Report) -> None:
    warmth = warmth_by_name(ds.tree, ds.ladder)
    bad = [
        (parent["name"], node["name"], warmth[parent["name"]], warmth[node["name"]])
        for node, parent in _edges(ds.tree)
        if parent is not None and not warmth[node["name"]] > warmth[parent["name"]]
    ]
    if bad:
        p, c, wp, wc = bad[0]
        r.fail(f"{len(bad)} edges not strictly warmer going down, e.g. {p} {wp:.3f} -> {c} {wc:.3f}")


def check_orderings(ds: Dataset, r: Report) -> None:
    warmth = warmth_by_name(ds.tree, ds.ladder)
    lineages = _lineages(ds.tree)

    def lca_warmth(a: str, b: str) -> float:
        shared = ""
        for x, y in zip(lineages[a], lineages[b]):
            if x != y:
                break
            shared = x
        return warmth[shared]

    checked = skipped = 0
    for chain in (ds.manifest.get("checks") or {}).get("closer") or []:
        anchor, order = chain["to"], chain["order"]
        if anchor not in lineages:
            skipped += len(order)
            continue
        present = [s for s in order if s in lineages]
        skipped += len(order) - len(present)
        scores = [(s, lca_warmth(anchor, s)) for s in present]
        for (near, hot), (far, cold) in zip(scores, scores[1:]):
            checked += 1
            if not hot > cold:
                r.fail(f"{anchor} vs {near} ({hot:.3f}) should beat {anchor} vs {far} ({cold:.3f})")
    if checked or skipped:
        r.note(f"orderings: {checked} checked, {skipped} skipped (not in the tree)")
    else:
        r.note("orderings: the manifest lists none")


def check_sizes(ds: Dataset, r: Report) -> None:
    if not ds.manifest.get("sizes"):
        return
    try:
        sizes = Sizes.from_manifest(ds.manifest["sizes"])
    except ValueError as e:
        r.fail(str(e))
        return
    assert sizes is not None
    lv = leaves(ds.tree)
    missing = [x["name"] for x in lv if "fame" not in x]
    if missing:
        r.fail(f"{len(missing)} leaves have no fame, which a sized tree needs, e.g. {missing[:3]}")
    if sizes.stops[-1] >= len(lv):
        r.fail(f"the last stop, {sizes.stops[-1]}, is not below the {len(lv)} leaves; the whole tree is the slider's end")
        return
    for stop in sizes.stops:
        cut = ds.at_size(stop)
        sub = Report(f"at {stop}")
        # Not the share of rank claims rejected: that is the data's, and a cut
        # keeps the high nodes where the rejections sit while it drops the
        # genera, so at 500 the whole tree's 1.4% read as 12%.
        check_edges(cut, sub)
        check_orderings(cut, sub)
        r.failures += [f"at {stop}: {f}" for f in sub.failures]
    r.note(f"sizes: {', '.join(map(str, sizes.stops))} and {len(lv)}, daily at {sizes.default}")


CHECKS = (check_shape, check_warmth, check_orderings, check_sizes)


def validate(ds: Dataset, checks=CHECKS) -> Report:
    report = Report(f"{ds.id}: {ds.manifest.get('title', '?')}")
    for check in checks:
        check(ds, report)
    return report
