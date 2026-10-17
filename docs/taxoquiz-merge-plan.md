# Merging TaxoQuiz into TreeQuiz — plan

*Drafted 17 Oct 2026. Not started; each phase below is meant to be one
session's work, landing green on both suites before the next begins.*

The goal: TreeQuiz becomes a superset of TaxoQuiz — its big-dataset pipeline,
TaxoQuiz Full's 41k animals, the Android app, and everything learned about
scraping Wikidata and feeding fixes back upstream — and gains two things
neither repo has: **choosing which trees live on the device** (download and
delete), and **a size slider** that grows a tree from its 500 best-known
leaves to all of them, each step more obscure.

## What TaxoQuiz has that TreeQuiz does not

| Area | In TaxoQuiz | Size |
|---|---|---|
| Big-dataset pipeline | `datagen/scraper.py`, `extract_game_tree.py`, `scrape_taxon_info.py`, `seed_taxon_info.py`, `authorities.py` (Catalogue of Life) | ~2,200 lines + tests |
| Audit and upstream loop | `audit_dataset.py` + `audit_template.html`, `upstream_check.py`, `upstream_leads.json` (the ledger), `UPSTREAM.md` | ~1,200 lines |
| Measurements | `datagen/SCALING.md` (fetch timings, page sizes, the subset property), `data/README.md` | docs |
| TaxoQuiz Full | `data/wikidata-parents-fixed/`: 41,153 species, 57,616 nodes. Tree 7.5MB (1.2MB gzipped), text 45.6MB (9.6MB gzipped). Caches in `data/_cache/` (143MB, regenerable, not committed) | data |
| Android | Capacitor 8, `frontend/android/` Gradle project, `standard`/`full` flavours, release signing from `~/.android/taxoquiz-release.jks`, `backButton.ts` (`useCloseOnBack`), launcher icons, CI's APK job | app |
| History | `CLAUDE.md` (1,790 lines), most of it display decisions that TreeQuiz already inherited | docs |

Already across: the engine, frontend, seeds, hints, bulk guessing, explore,
the phone layout, the curated 530-species example (`datasets/animals`), and
TaxoQuiz's `explore-jump-fix` branch (ported, still unmerged there).

## The slider — how it works

TaxoQuiz sized its datasets by `MIN_SITELINKS`: a species is in when at least
that many Wikipedias cover it. A species' sitelink count does not depend on
the query, so **every smaller dataset is exactly a subset of every bigger
one** (measured in `SCALING.md`: `>=10` plus the `[6,10)` band is exactly
`>=6`). That makes one tree enough for every size:

- **The builder writes a `fame` on every leaf** (its sitelinks). The tree
  ships whole, once.
- **The engine cuts it**: keep the N leaves with the highest fame (ties by
  name, so both engines agree), drop internal nodes left with no leaves. This
  is the threshold rule exactly, restated as a count. It is a new engine
  function, so it goes in Python first, then the port, then conformance cases
  at a few N.
- **Measured on Full**:

  | N | fewest sitelinks | nodes |
  |---:|---:|---:|
  | 500 | 64 | 1,692 |
  | 1,000 | 49 | 2,795 |
  | 2,000 | 38 | 4,749 |
  | 5,000 | 28 | 9,561 |
  | 10,000 | 23 | 16,613 |
  | 20,000 | 15 | 29,605 |
  | 41,153 | 6 | 57,616 |

- **A manifest opts in** with `"sizes": {"min": 500, "default": 2000}`; any
  tree whose leaves carry `fame` gets the slider. Plants, cities, languages,
  chemistry and physics already choose leaves by sitelinks, so each could
  later lower its threshold and ship fame too — no app change.
- **The slider is logarithmic** with snapping stops (500, 1k, 2k, 5k, 10k,
  20k, all): 500→600 matters, 30,000→30,100 does not.
- **The size is part of the game's identity.** The seed fingerprint already
  covers the leaf names, so a seed dealt at 2,000 is rejected at 5,000; the
  share link gains `&n=2000` and applies it. **The daily is always the
  manifest's default size**, so everyone plays the same one. Rounds, tallies
  and records are keyed per tree *and* size.
- **Popup text is sharded by when a node enters.** A node's entry point is the
  rank of its most famous leaf, so text can be split into tiers matching the
  stops (`info-500.json`, `info-1000.json`, …). Playing at 2,000 needs only the
  first three tiers, ~8% of the 9.6MB. Without this, every size costs the
  whole 45MB text.
- **Known difference from a real rebuild**: TaxoQuiz's display names depend on
  the species set (a "group word" is one ≥5 species end in), so a tree cut at
  N can name a few species differently from a scrape at that threshold. The
  cut tree is the honest one to play — the names come from the full build —
  but it is a documented difference, not a bug.

## Download and delete

Today TreeQuiz bundles every tree into the build (`import.meta.glob`), and
the service worker's precache is versioned per build, so anything stored
there is wiped by the next deploy. Both have to change:

- **A catalogue** (`datasets.json`, emitted by the build) lists every tree:
  id, manifest, version (a content hash), and the size of each file and info
  tier. The front page reads it, so a tree not yet downloaded still shows,
  with its size.
- **Downloads live in their own cache** (`treequiz-data`, Cache Storage),
  keyed by file URL, which carries the content hash. It is outside the
  build's versioned cache, so a deploy never deletes a download. Same code on
  the website and in the app: Capacitor serves from `https://localhost`, a
  secure context with Cache Storage, and GitHub Pages answers with
  `Access-Control-Allow-Origin: *`.
- **Small trees download themselves on first open**, as they effectively do
  now; anything over a threshold (say 5MB) asks first and says how much.
  A **Manage trees** screen lists each with what it takes on the device and a
  Delete button; deleting also offers to clear its saved round. The site asks
  for `navigator.storage.persist()` once something big is downloaded, so the
  browser does not evict it.
- **A newer version on the server** shows as "Update (1.2MB)"; the old copy
  keeps playing until the player takes it, since a saved round's seed belongs
  to the old tree.
- **In the APK**, the small trees are bundled (all nine are ~1.5MB gzipped),
  so it works offline from install; big trees download from the Pages site.
  A bundled tree can be hidden, not deleted — it is part of the APK.

## Phases

1. **Bring the knowledge across** (docs only). TaxoQuiz's `SCALING.md`,
   `UPSTREAM.md`, `data/README.md` and the CLAUDE.md sections that are not
   already here (dataset sizing, validation history, audit, website, Android)
   move into `docs/` and `datagen/`, edited to TreeQuiz's names. TaxoQuiz's
   README gains a pointer here; the repo is archived once phase 4 lands.
2. **Port the pipeline.** TaxoQuiz's datagen becomes `datagen/animals_full/`
   (the scraper is animal-specific: Linnaean ranks, Catalogue of Life,
   binomials), with its tests, behind a `build_animals_full.py` that converts
   to TreeQuiz's shape as `build_animals.py` does, adds `fame`, and writes
   `datasets/animals-full/`. Its caches go in `datagen/_cache/`, gitignored.
   Rebuilt from TaxoQuiz's existing caches, so no rescrape.
3. **The slider.** `cut(tree, n)` in `src/treequiz/` and its port, conformance
   cases, the manifest's `sizes`, the slider on the front page, `&n=`, per-size
   keys, sharded info.
4. **Download and delete.** The catalogue, the data cache, Manage trees, the
   service worker changes, Pages publishing the big tree.
5. **Android.** Capacitor back in, the Gradle project from TaxoQuiz renamed
   (`io.github.markharley12.treequiz` — a new app ID, since TaxoQuiz's is a
   different app), `backButton.ts`, icons, release signing with a new key or
   TaxoQuiz's, CI's APK job. One flavour: the download screen replaces
   TaxoQuiz's separate Full app.
6. **Upstream, generalised.** The ledger and `upstream_check.py` made
   per-dataset (`datagen/upstream/<id>.json`), seeded with the leads every
   builder already found by hand: instruments' three `CODE_FIXES`, copper(II)
   oxide, plants' fifteen `PARENTS`, cities' bulk-made sitelinks (Monte
   Águila). The animal-specific audit checks (group words, range maps,
   synonyms via COL) stay animal-specific; the general ones (a label that is a
   group word, a sitelink to the wrong article, a picture that is a map) run
   on any Wikidata-backed tree.

Phases 1 and 2 are independent of 3–5; 3 and 4 are independent of each other;
5 needs 4 (the app downloads what Pages publishes).

## Decided (17 Oct 2026)

- **Big data lives in GitHub Release assets**, not git. TaxoQuiz committed
  Full (~57MB of history per refresh). Here `datasets/animals-full/` commits
  only its hand-written `manifest.json`; `tree.json` and the info tiers are
  built locally, uploaded to a release by a script, and fetched by the Pages
  workflow before building.
- **TaxoQuiz's history is not imported.** Files are ported; TaxoQuiz is
  archived with a pointer here once the Android app has moved.
- **Two animals trees.** The curated 530 is a hand-built NCBI-style tree, not
  a subset of Wikidata's, so it cannot be the slider's 500 end. It stays as
  "Animals", bundled; `animals-full` sits beside it with the slider.
- **Phases 1–2, 3 and 4 run in parallel**, one session each on its own
  branch, Android after.

## The contract between the parallel phases

So the three sessions agree without waiting on each other:

- A leaf may carry **`fame`**: a non-negative integer, higher is better known
  (sitelinks, for every Wikidata tree). Cut order is fame descending, then
  `name` ascending.
- A manifest may carry **`sizes`**: `{"min": 500, "default": 2000, "stops":
  [500, 1000, 2000, 5000, 10000, 20000]}`; the max (and last stop) is the
  tree's leaf count. Only meaningful when every leaf has `fame`. The slider
  snaps to the stops; info tiers are cut at them.
- Popup text for a sized tree may be split into **tiers**:
  `info-<n>.json` holds the nodes that first appear when the tree is cut to
  `n` (and not at the previous stop). An unsized tree keeps one `info.json`.
- **`datasets/<id>/` with a manifest but no `tree.json` locally** is a remote
  tree: its files come from the release. Phase 2 makes the files, phase 4
  makes the app and Pages fetch them; phase 3 cuts whatever tree it is given.
