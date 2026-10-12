"""`treequiz` — list, validate and play datasets from a terminal.

    treequiz list
    treequiz validate [ID ...] [--all]
    treequiz play ID [--seed SEED | --daily]
    treequiz odd ID [--seed SEED | --daily]           # odd one out
    treequiz state ID SECRET [GUESS ...] [--hints N]    # the raw JSON
    treequiz explore ID [ROOT] [--budget N]
"""
from __future__ import annotations

import argparse
import json
import sys

from . import dataset, explore, game, odd
from .validate import validate


def _bar(warmth: float, width: int = 10) -> str:
    filled = round(warmth * width)
    return "█" * filled + "·" * (width - filled)


def render(state: dict | None) -> str:
    """The display tree as indented text, single-child chains joined with ›."""
    if state is None:
        return "(nothing guessed yet)"
    lines: list[str] = []

    def walk(node: dict, indent: int) -> None:
        chain = [node]
        while len(chain[-1]["children"]) == 1 and chain[-1]["node_type"] == "ancestor":
            chain.append(chain[-1]["children"][0])
        end = chain[-1]
        text = " › ".join(n["label"] for n in chain)
        if end["node_type"] == "guess":
            text += f"   {_bar(end['lca_warmth'])} {round(100 * end['lca_warmth'])}%"
        lines.append("  " * indent + text)
        for child in end["children"]:
            walk(child, indent + 1)

    walk(state, 0)
    return "\n".join(lines)


def cmd_list(_: argparse.Namespace) -> int:
    for ds_id in dataset.available():
        ds = dataset.load(ds_id)
        s = explore.stats(ds)
        print(f"{ds_id:<12} {s['leaves']:>6} {ds.manifest.get('noun_plural', 'leaves'):<10} "
              f"depth {s['max_depth']:<3} {ds.title}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    ids = dataset.available() if args.all or not args.ids else args.ids
    worst = 0
    for ds_id in ids:
        report = validate(dataset.load(ds_id))
        print(report.render() + "\n")
        worst = max(worst, 0 if report.ok else 1)
    return worst


def cmd_state(args: argparse.Namespace) -> int:
    ds = dataset.load(args.id)
    print(json.dumps(game.get_game_state(ds, args.secret, args.guesses, args.hints), indent=2))
    return 0


def cmd_explore(args: argparse.Namespace) -> int:
    ds = dataset.load(args.id)

    def walk(node: dict, indent: int) -> None:
        more = " +" if node["truncated"] else ""
        rank = f"[{node['rank']}] " if node["rank"] else ""
        print(f"{'  ' * indent}{rank}{node['label']}  ({node['leaf_count']}){more}")
        for c in node["children"]:
            walk(c, indent + 1)

    walk(explore.subtree(ds, args.root, budget=args.budget), 0)
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    ds = dataset.load(args.id)
    secret, seed = game.pick(ds, seed=args.seed, daily=args.daily)
    noun = ds.noun
    print(f"{ds.title} — guess the secret {noun}.  Seed {seed}")
    print("Type part of a name for suggestions; '?' for a hint, '!' to give up.\n")
    guesses: list[str] = []
    hints = 0
    while True:
        try:
            raw = input("> ").strip()
        except EOFError:
            print()
            return 0
        if not raw:
            continue
        if raw == "!":
            print(f"The answer was {secret}.")
            return 0
        if raw == "?":
            hints += 1
            print(render(game.get_game_state(ds, secret, guesses, hints)))
            continue
        options = game.suggest(ds, raw, limit=10, exclude=guesses)
        exact = [o for o in options if o.lower() == raw.lower()]
        if not exact:
            if not options:
                print(f"  no {noun} matches {raw!r}")
            else:
                print("  " + "\n  ".join(options))
            continue
        guesses.append(exact[0])
        print(render(game.get_game_state(ds, secret, guesses, hints)))
        if exact[0] == secret:
            print(f"\nYou got it in {len(guesses)}{f' with {hints} hints' if hints else ''}.")
            return 0


def cmd_odd(args: argparse.Namespace) -> int:
    ds = dataset.load(args.id)
    seed = args.seed or odd.pick_seed(ds, daily=args.daily)
    puzzles = odd.make_set(ds, seed)
    print(f"{ds.title} — odd one out. Seed {seed}")
    print("Two of each three share a group the third is not in. Type 1, 2 or 3.\n")
    right = 0
    for i, p in enumerate(puzzles, 1):
        print(f"{i}/{len(puzzles)}  " + "   ".join(f"{k}. {c}" for k, c in enumerate(p["choices"], 1)))
        while True:
            try:
                raw = input("> ").strip()
            except EOFError:
                print()
                return 0
            if raw in ("1", "2", "3"):
                break
        ok = odd.check(p, p["choices"][int(raw) - 1])
        right += ok
        a, b = p["pair"]
        print(f"  {'Right' if ok else 'No'}: {a} and {b} share {p['group']['label']}; "
              f"{p['odd']} meets them only at {p['shared']['label']}.\n")
    print(f"{right} of {len(puzzles)}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="treequiz", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    v = sub.add_parser("validate")
    v.add_argument("ids", nargs="*")
    v.add_argument("--all", action="store_true")
    v.set_defaults(fn=cmd_validate)
    p = sub.add_parser("play")
    p.add_argument("id")
    p.add_argument("--seed")
    p.add_argument("--daily", action="store_true")
    p.set_defaults(fn=cmd_play)
    o = sub.add_parser("odd")
    o.add_argument("id")
    o.add_argument("--seed")
    o.add_argument("--daily", action="store_true")
    o.set_defaults(fn=cmd_odd)
    s = sub.add_parser("state")
    s.add_argument("id")
    s.add_argument("secret")
    s.add_argument("guesses", nargs="*")
    s.add_argument("--hints", type=int, default=0)
    s.set_defaults(fn=cmd_state)
    e = sub.add_parser("explore")
    e.add_argument("id")
    e.add_argument("root", nargs="?")
    e.add_argument("--budget", type=int, default=40)
    e.set_defaults(fn=cmd_explore)
    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
