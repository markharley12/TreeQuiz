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

Eight datasets — **maths** (MSC2020, 517 fields), **languages** (Glottolog,
415), **instruments** (Hornbostel–Sachs, 428), **animals** (TaxoQuiz's 530),
**chess** (Lichess, 446 openings), **physics** (PhySH, 487 topics),
**chemistry** (ChEBI, 465 chemicals), **cities** (Wikidata and Natural
Earth, 626). Two games: the guessing round and odd one out. Python suite
176 tests, frontend 475, both green;
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
cases. Every case is a whole game state or slice, so each dataset costs about
150KB: chess took the file past 1MB, and the counts were cut (Oct 2026) to the
fewest that reach every rule — 9 random rounds plus the specials, the 200-node
slice only from the top, the suggest exclusion list written once. 769KB with
five, 1,055KB with seven, 1,127KB with eight: trim again if it passes about
1.2MB. The cut was checked by mutation and found an old gap: a child landing
*exactly* on its parent's warmth (`<=` against `<` in the floor) was reached by
no case; the synthetic `C0`/`P`/`C` tree now reaches it.

## Odd one out — the second game

`src/treequiz/odd.py` (reference), `frontend/src/engine/odd.ts` (port),
both in the conformance file. Three leaves; a rooted tree says exactly which
two are closer, or that none is, so puzzles are built top-down (meeting
node, a child for the pair, another for the odd one) and are resolved by
construction. Difficulty is the meeting node's warmth, by thirds of the
tree's ranking; a set of ten runs 3 easy, 4 medium, 3 hard. Meeting nodes
are drawn **in proportion to their leaves**: drawn evenly, languages' tiny
families made "easy" puzzles of Chechen, Ingush and Rutulian. Every choice
is `seed.draw(key, n)` (sha256 of a key, mod n), so a seed is the whole set
in both engines; `seed.body_of` and `draw` were factored out of `resolve`
for it. The reveal (`oddReveal.ts`, display only) draws the three as a
little tree: where all three meet, the pair's group, the leaves, each box
carrying the labels it skips. Links are `?d=<id>&odd=<seed>`; the set in
progress is `treequiz:odd:<id>`, the tally `treequiz:oddtally:<id>`, and
`view:<id>` remembers odd one out as it does explore.

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
- **A search jump in explore landed nowhere.** The node is not in the DOM on
  the commit the tree arrives, so the focus effect now retries per frame. And
  the breadcrumbs the jump adds resize the tree, which re-framed it, so the
  jumped-to node is kept in the middle through a resize (`jumped`) until a
  pan, tap, re-root or expand-all. TaxoQuiz had it too, on the first jump of
  a visit (Homo sapiens at (-353, 1222), off the view); the port is on
  TaxoQuiz's `explore-jump-fix` branch, not merged.
- **A link to the round already saved resumes it**, even when explore was the
  tree's last view. Remembering explore per tree is TreeQuiz's, and it used
  to win over the link.
- **At 390px every round control fits two rows**: "New" for "New
  instrument", no "Seed" caption, and slimmer seed-row buttons.
- **`chain_order: "root_first"`** in a manifest, for a tree whose labels are
  steps of a path (chess moves). `compress` still joins deepest first with
  " › ", since `findAnchor` and the popup split on it; `chainText` reverses the
  steps for display only, and `chain_trim` (a JS pattern) comes off every step
  but the first, so "2.Nf3" then "2…Nc6" read "2.Nf3 Nc6". In such a tree the
  root is not merged into its child ("Start 1.e4" read badly), and the give-up
  sentence and the bulk-guess header name a group by its whole path
  (`pathText`), since its own label is only the last step.
- **A popup entry may carry a `subtitle`** — a chess opening's moves — set
  under the title. And the source's licence line now needs text to follow:
  a board drawn by the builder is nobody's CC BY-SA.
- **Pictures sit on a white mat** (`IMAGE_MAT`), not TaxoQuiz's black:
  Wikipedia's chemical structures are transparent line drawings, and on black
  the caffeine popup showed an empty black box.
- **The picker balances its rows**, at most four across: five trees are three
  and two, not four and a stray.
- **Results and stats** (`results.ts`, Oct 2026): a finished round shares as
  squares by warmth band, ten to a line, capped at 50 (a bulk guess can spend
  100). Dailies are kept per tree under `treequiz:daily:<id>`, keyed by day,
  first finish only, and the entry is the whole round (seed, guesses,
  warmths), so the front page can show today's result after a practice round
  has replaced the saved session. A finished daily is never dealt twice: the
  daily button opens the stats instead, and a daily in progress *resumes*
  (it used to restart from nothing). Streaks count calendar days in UTC, as
  the daily's seed does, and survive until today is over.

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
- **Chess** (`build_chess.py`, whose docstring has every decision): Lichess's
  CC0 list, pinned to a commit. The tree is the moves: positions are internal
  nodes named by their line, each opening a leaf under the position it names,
  a position with one way on merged into the next, so depth counts branch
  points. Kept: every family, every variation with a named subline, and `ALSO`
  (the Fried Liver, the Sveshnikov…) — 446 of 3,177 names. Leaves are ranked
  by ECO code, positions "Position". Every node's popup is its board, an SVG
  data URL of ~800 bytes drawn with the system's chess glyphs; 650 of them
  gzip from 850KB to ~30KB, since boards differ only in their pieces. 102
  openings have Wikipedia text: titles are guessed, so see the datagen README
  for what a guess must pass. Moves are replayed by `san.py`, stdlib only, and
  verified once against python-chess on all 3,865 Lichess lines (positions and
  last moves equal); its castling now refuses a blocked or attacked path, which
  that check could not have caught, since Lichess's moves are all legal.
- **Physics** (`build_physics.py`, whose docstring has every decision): PhySH,
  the APS's Physics Subject Headings, CC0. Disciplines, then the Research
  Areas and Physical Systems facets (techniques and professional topics left
  out; the facet is not a level, being a filing category). PhySH is a
  lattice, so each concept takes its deepest broader concept, ties to the one
  with more beneath it, and a top concept the discipline with fewest tops.
  Fame is a Wikipedia article named for the label (give or take a plural), or
  a whole-page redirect that does not broaden it, at ≥25 sitelinks; `TITLES`
  maps 21 compound labels ("Neutron stars & pulsars") by hand, since taking a
  part by rule found *Light* for "Quantum information with atoms & light".
  Left out: Networks, the living systems' biology objects (DNA, sperm), and
  `PRUNE` (paints, cosmetics). A famous concept with one child becomes the
  leaf, or splicing would lose it — black holes did.
- **Chemistry** (`build_chemistry.py`, whose docstring has every decision):
  ChEBI's is_a classes, release 255 pinned. Leaves are Wikidata items with a
  ChEBI ID, ≥45 sitelinks, and an InChIKey (a compound, not a class) or
  element status; an element maps to its "X atom" term, by name where
  Wikidata gives none. ChEBI is a lattice, so the deepest parent wins, but
  never a class by behaviour where a structural one exists (`NOT_STRUCTURE`:
  "gas molecular entity" pulled the noble gases away from the other atoms).
  `CHEBI_FIXES` corrects copper(II) oxide, which Wikidata files as "CU-O
  LINKAGE" — a lead for fixing Wikidata. Lost by the rule: glucose,
  penicillin, chlorophyll, which Wikidata files as classes.
- **Cities** (`build_cities.py`, whose docstring has every decision):
  World → continent → subregion → country → first-level region → city.
  Continents and subregions are Natural Earth's (public domain), which
  follow the UN geoscheme without the UN's licence; a country sits whole
  in one continent, so Russia and Novosibirsk are Europe, Turkey Asia.
  Cities are Wikidata's *city* subclasses **plus** any settlement or
  municipality of ≥50k people: Madrid is only a "municipality of Spain"
  there, and *city* alone lost 34 famous ones. A place inside another
  chosen city (Manhattan, Hollywood) is dropped. A region is the country's
  usual kind of first-level unit, nearest first; a city in two regions or
  two countries (Jerusalem) sits higher. Sitelinks are noisy here: bots
  inflate Brazilian municipalities (Osasco makes the cut, Córdoba in
  Argentina does not).
- **Rejected**: countries on UN M49 — the UN's terms forbid redistribution and
  derivative works.
