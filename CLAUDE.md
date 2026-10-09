# TreeQuiz

The game from [TaxoQuiz](../TaxoQuiz) — guess a secret leaf, scored by its
lowest common ancestor with each guess — generalised to any tree. Started Oct
2026 by abstracting TaxoQuiz: its engine, frontend, seeds, hints, bulk guessing,
explore mode and phone layout came across, and every word about biology became
a manifest field. TaxoQuiz's CLAUDE.md holds the history behind most display
decisions here (why the colour scale is absolute, why vertical distance is
depth, why the game view follows the newest guess…); they carried over
unchanged, and this file covers what is new.

## Status

Four datasets — **maths** (MSC2020, 517 fields), **languages** (Glottolog, 415),
**instruments** (Hornbostel–Sachs, 428), **animals** (TaxoQuiz's 530). Python
suite 106 tests, frontend 369, both green;
CI and Pages workflows written but **the repo has not been pushed** and has no
GitHub remote yet. No Android build (TaxoQuiz's Capacitor setup was left out).

Run with `env -u PYTHONPATH` on this machine: ROS's `PYTHONPATH` drags its own
pytest plugins in and collection aborts (`No module named 'osrf_pycommon'`).

```bash
env -u PYTHONPATH .venv/bin/python -m pytest -q
env -u PYTHONPATH .venv/bin/python tests/conformance.py     # after engine or dataset changes
cd frontend && npm test && npm run lint && npx tsc --noEmit
```

## What a dataset is

`datasets/<id>/{manifest,tree,info}.json`; see `src/treequiz/dataset.py` for
every field. The frontend finds them with `import.meta.glob` in
`frontend/src/engine/datasets.ts`, so a new directory is a new tree in the app
with no code change. Nothing in `src/` or `frontend/src/` may name a dataset —
words come from the manifest (`frontend/src/words.ts`).

Manifests are hand-written and builders never touch them. `checks.closer` is the
data's test: orderings of relatedness that a correct tree must reproduce,
keyed by node **name**, since labels drift.

## Warmth — what changed from TaxoQuiz's `ranks.py`

`src/treequiz/ladder.py`. The Linnaean `LEVELS` table moved into the animals
manifest; the algorithm (believed ranks, interpolation, strictly warmer going
down) is TaxoQuiz's, plus three changes, all documented in the module:

- **Root pinned at 0, leaves at `top`**, whatever their ranks say. TaxoQuiz got
  both for free from a kingdom root and species leaves.
- **A ladder is optional.** With none, warmth is the fraction of the way down
  the longest path below — languages run this way, and all 23 of their ordering
  checks pass on shape alone.
- **Ties below go to the longer path.** TaxoQuiz took the first child, so warmth
  depended on sort order. On the animals tree this moved 2 of 1,615 nodes
  (Eumetazoa, Bilateria), measured against TaxoQuiz's `rank_levels`.

## The engine runs twice

As in TaxoQuiz: Python is the reference, `frontend/src/engine/` the port, and
`tests/conformance.py` writes `conformance.json` over **every shipped dataset**
plus synthetic trees. Adding or rebuilding a dataset therefore means
regenerating it; `conformance.test.ts` also fails if a shipped dataset has no
cases. The file is ~780KB with four datasets — watch it if many are added.

## Frontend decisions new here

- **A round per tree.** Sessions are keyed `treequiz:session:<id>`; `App` keys
  `Round` on the dataset so a switch remounts it with that tree's state. Home no
  longer throws the round away (TaxoQuiz's "Change mode" did); the front page
  offers Resume. Explore is a separate key, so exploring never overwrites a round.
- **Share links carry the tree**: `?d=maths&seed=…`, applied in `main.tsx`
  before the first render. A bare seed rejected by the current tree is looked
  up by its fingerprint across all trees (`datasetForSeed`), which loads every
  tree — only done after a rejection.
- **`long_labels`** in a manifest widens both trees' boxes by 64px; game labels
  wrap to two lines everywhere. MSC section names are phrases, and at TaxoQuiz's
  176px they were cut to "Boundary value problem…".
- `api.ts` has no server path any more; TaxoQuiz's FastAPI layer was not ported.
- **`hide_names`** in a manifest keeps node names out of sight — explore's
  second line, its search results, the popup's subtitle. For instruments and
  languages the names are Wikidata and Glottolog IDs, which say nothing to a
  player.
- **A suggestion found by an alias says which** (`aliasHint.ts`): "fiddle"
  offers the xylophone for its alias "straw fiddle", and without the alias
  beside it the row reads as a mistake. Display only, so no Python twin.
- **The popup's licence is `info_source`'s**, not the first source's
  (`words.infoSource`). The first is usually the tree's: languages popups
  credited Wikipedia's CC BY-SA text to Glottolog's CC BY until Oct 2026.
- **Two bugs found here that TaxoQuiz probably shares**, since the code came
  across unchanged:
  - **A search jump in explore landed nowhere.** The node is not in the DOM on
    the commit the tree arrives, so the focus effect now retries per frame.
    And the breadcrumbs the jump adds resize the tree, which re-framed it, so
    the jumped-to node is kept in the middle through a resize (`jumped`)
    until a pan, tap or re-root.
  - **A link to the round already saved opened explore** when explore was the
    tree's last view. It resumes the round now.
- **At 390px every round control fits two rows**: "New" for "New
  instrument", no "Seed" caption, and slimmer seed-row buttons.

## Data notes

- **Maths**: the branch/area layer above MSC's subjects is ours (`BRANCHES` in
  `build_maths.py`) — MSC has none, and without it the tree is flat. `00`, `01`,
  `97` are left out (writing *about* maths). Vague section names are qualified
  (`QUALIFY`). The CSV is Latin-1 with non-Latin-1 letters lost to `?`; `REPAIRS`
  restores ten, checked against `MSC_2020.tex`, and the build fails on a new one.
  Licence CC BY-NC-SA: non-commercial.
- **Languages**: Glottolog is a splitter and Wikidata files famous names on
  subgroups and dialects. A famous dialect names its language (derived); a
  famous subgroup names its standard variety (`STANDARD_VARIETY`, checked).
  Without both, Persian, Arabic, Hebrew and Swahili were missing.
- **Animals** is converted from TaxoQuiz's committed example by
  `build_animals.py`; it reads `../TaxoQuiz` by default.
- **Instruments** (`build_instruments.py`, whose docstring has every decision):
  Wikidata's P1762 codes at ≥12 sitelinks; class names from Wikipedia's four
  *List of …phones by Hornbostel–Sachs number* articles, which win over the
  main article because they use the numbering Wikidata does (the main article
  disagrees on drum shapes and brass bores). Names are tidied to read out of
  context (`tidy`, `LABELS`), and the build **fails** on a relative name such
  as "With fingerholes" that has no label, so a new threshold asks for one.
  Electrophones follow the 2011 MIMO revision, which no article lists: names
  only, since the popup credits its text to Wikipedia. Three codes are
  corrected by hand (`CODE_FIXES`): the bayan, the Appalachian dulcimer and
  the music box. They are upstream errors, and leads for fixing Wikidata.
  An electric guitar shares only the root with a guitar. That is the
  classification (electrophones are a class of their own), not a bug.
- **Rejected**: countries on UN M49 — the UN's terms forbid redistribution and
  derivative works.
