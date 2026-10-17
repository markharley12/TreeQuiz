#!/usr/bin/env python3
"""Publish a remote tree's built files as a GitHub Release.

A tree too big for git (animals-full: a 6MB tree and 39MB of popup text)
commits only its hand-written manifest. The manifest's `release` names a
GitHub Release, and the Pages workflow downloads that release's assets into
`datasets/<id>/` before it builds — so the assets are named exactly as the
files sit there (`tree.json`, `info.json`, `info-<n>.json`), and the manifest
is not among them, since git already has it.

**A tag is never reused.** New data is a new tag: edit `release` in the
manifest (by convention `<id>-<yyyy-mm-dd>`, the day it is published), run
this, and commit the manifest. Replacing the files under a published tag
would change a tree under everyone's saved rounds without the manifest
saying so, so a tag that exists is refused unless `--clobber` says otherwise.

Without `--yes` this only checks the files and says what it would run.
Publishing is the owner's call: it puts the data on GitHub under their name.

Usage:
    python3 datagen/publish_release.py animals-full          # check, show the plan
    python3 datagen/publish_release.py animals-full --yes    # publish
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from common import REPO, dataset, read_json, validate
from treequiz.tree import leaves


def files_for(ds_id: str) -> tuple[dict, list]:
    out = REPO / "datasets" / ds_id
    manifest = read_json(out / "manifest.json")
    if not manifest.get("release"):
        raise SystemExit(f"{ds_id}'s manifest names no `release`: it ships in git, not as a release")
    if not (out / "tree.json").is_file():
        raise SystemExit(f"{out / 'tree.json'} is missing: build it first")
    tier = lambda f: int(f.stem.split("-")[1]) if "-" in f.stem else 0  # noqa: E731
    files = [out / "tree.json", *sorted(out.glob("info*.json"), key=tier)]
    return manifest, files


def check(ds_id: str, manifest: dict, files: list) -> list[str]:
    """What is wrong with the files, as the app would find it."""
    problems = []
    report = validate(dataset.load(ds_id))
    if not report.ok:
        problems += report.failures
    sizes = manifest.get("sizes")
    if sizes:
        count = len(leaves(dataset.load(ds_id).tree))
        want = {f"info-{s}.json" for s in [*sizes.get("stops", []), count] if s <= count}
        have = {f.name for f in files if f.name.startswith("info-")}
        if want != have:
            problems.append(f"info tiers {sorted(have)} are not the manifest's stops {sorted(want)}: rebuild")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset")
    ap.add_argument("--yes", action="store_true", help="publish; without it, only say what would run")
    ap.add_argument("--clobber", action="store_true", help="replace the assets of a tag that exists")
    args = ap.parse_args()

    manifest, files = files_for(args.dataset)
    tag = manifest["release"]
    problems = check(args.dataset, manifest, files)
    if problems:
        raise SystemExit("refusing to publish:\n  " + "\n  ".join(problems))

    total = sum(f.stat().st_size for f in files)
    print(f"{args.dataset} -> release {tag}")
    for f in files:
        print(f"  {f.name:<20} {f.stat().st_size / 1e6:6.1f}MB")
    print(f"  {'total':<20} {total / 1e6:6.1f}MB")

    if not shutil.which("gh"):
        raise SystemExit("needs the GitHub CLI, gh")
    exists = subprocess.run(["gh", "release", "view", tag], cwd=REPO, capture_output=True).returncode == 0
    if exists and not args.clobber:
        raise SystemExit(f"release {tag} exists. New data takes a new tag: change `release` in "
                         f"datasets/{args.dataset}/manifest.json (or pass --clobber to replace its files)")
    paths = [str(f) for f in files]
    if exists:
        cmd = ["gh", "release", "upload", tag, *paths, "--clobber"]
    else:
        notes = (f"Built files for datasets/{args.dataset}, made by datagen/. The Pages workflow "
                 f"downloads them into datasets/{args.dataset}/ before building; the manifest is in git.")
        cmd = ["gh", "release", "create", tag, *paths, "--title", f"{manifest['title']} data ({tag})",
               "--notes", notes, "--latest=false"]
    shown = [c[len(str(REPO)) + 1:] if c in paths else (f"'{c}'" if " " in c else c) for c in cmd]
    print("\n" + " ".join(shown))
    if not args.yes:
        print("\nnot run: pass --yes to publish")
        return
    sys.exit(subprocess.run(cmd, cwd=REPO).returncode)


if __name__ == "__main__":
    main()
