"""What every builder shares: where datasets go, how they are written, and the
checks a tree must pass before it is.

A builder's job is to turn a source into `tree.json` (and optionally
`info.json`) in the shape `treequiz.dataset` documents. The manifest is written
by hand and committed; a builder never touches it, so the words a person chose
for a dataset cannot be overwritten by a rebuild.

Two rules, both carried over from TaxoQuiz, where a long scrape made them
matter:

1. **Every write is atomic** (`write_json_atomic`), so an interrupted build
   leaves the previous dataset whole.
2. **A tree is validated before it is written**, shape and warmth at least,
   and a failing tree is refused. The orderings in the manifest are checked
   too, since the manifest is already there.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from treequiz import dataset  # noqa: E402
from treequiz.jsonio import read_json, write_json_atomic  # noqa: E402
from treequiz.validate import validate  # noqa: E402

CACHE = REPO / "datagen" / "_cache"
USER_AGENT = "TreeQuiz-datagen/0.1 (https://github.com/markharley12/TreeQuiz)"


def fetch(url: str, dest: Path, *, refresh: bool = False) -> Path:
    """Download `url` to `dest` once; later builds read the copy."""
    if dest.exists() and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        while chunk := resp.read(1 << 16):
            out.write(chunk)
    tmp.replace(dest)
    return dest


def node(name: str, rank: str | None = None, label: str | None = None,
         children: list[dict] | None = None, aliases: list[str] | None = None) -> dict:
    """A tree node with only the fields that carry something, in a stable
    key order so rebuilt files diff cleanly."""
    out: dict = {"name": name}
    if label is not None and label != name:
        out["label"] = label
    if rank:
        out["rank"] = rank
    if aliases:
        out["aliases"] = aliases
    if children:
        out["children"] = children
    return out


def collapse_lone_children(tree: dict, keep: set[str] = frozenset()) -> dict:
    """Splice out internal nodes with exactly one child, except the root and
    any named in `keep`. A pass-through is never anyone's LCA and is joined
    onto its child on screen anyway, so it costs a name to read and adds no
    information; TaxoQuiz's clade layer left out Parahoxozoa for this reason."""
    def fix(n: dict, is_root: bool) -> dict:
        kids = n.get("children") or []
        while len(kids) == 1 and not is_root and n["name"] not in keep:
            n = kids[0]
            kids = n.get("children") or []
        if kids:
            n = {**n, "children": [fix(c, False) for c in kids]}
        return n
    return fix(tree, True)


def write_dataset(ds_id: str, tree: dict, info: dict | None = None, *, force_info: bool = True) -> None:
    """Validate `tree` against the committed manifest, then write it."""
    out = REPO / "datasets" / ds_id
    manifest_path = out / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"{manifest_path} is missing: write the manifest by hand first")
    manifest = read_json(manifest_path)
    report = validate(dataset.from_tree(tree, manifest, ds_id))
    print(report.render())
    if not report.ok:
        raise SystemExit(f"refusing to write {ds_id}: the tree fails validation")
    write_json_atomic(out / "tree.json", tree, indent=None)
    if info is not None and force_info:
        write_json_atomic(out / "info.json", info, indent=None)
    print(f"wrote {out}/tree.json" + (" and info.json" if info is not None else ""))
