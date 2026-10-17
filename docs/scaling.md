# Sizing animals-full, and growing it without rebuilding

*From TaxoQuiz's `datagen/SCALING.md` (measured 4 Sep 2026 against the live
Wikidata and Wikipedia endpoints) and the "Sizing a scrape" notes in its
CLAUDE.md, with the slider's measurements added in Oct 2026. Where a figure is
an estimate it says so. Paths are TreeQuiz's: the scripts are in
`datagen/animals_full/`, the caches in `datagen/_cache/animals-full/_raw/`.*

The question this answers: the tree we have is a subset of any bigger one we
would build, so what actually has to be fetched? And the same fact, read the
other way, is what lets one tree serve every size on the slider.

## 1. Fame is a property of the species

`scraper.py` keeps a species when at least `--min-sitelinks` Wikipedias have an
article on it. That count belongs to the species, not to the query, so the set
at threshold *N* is a strict subset of the set at any lower threshold, and the
difference is exactly the band between. Verified against Wikidata, not assumed:

| Query | Species (all of life) |
|---|---:|
| `>= 6` | 63,712 |
| `>= 10` | 41,648 |
| `[6, 10)` (the band) | 22,064 |
| **`>= 10` + band** | **63,712, exact** |

`tests/test_animals_full_scraper_incremental.py::test_band_plus_existing_equals_a_full_fetch`
holds this offline.

Counts across all life at other thresholds (`>= 4` and `>= 5` could not be
counted: the endpoint returned 502, then a read timeout, while `>= 3` succeeded
moments later; a failed COUNT is load, not "no data"):

| Threshold | Species |
|---:|---:|
| 3 | 77,052 |
| 6 | 63,712 |
| 8 | 51,276 |
| 10 | 41,143–41,648 |
| 20 | 17,809 |
| 30 | 6,186 |
| 50 | 1,486 |
| 75 | 508 |

Animalia is about two thirds of each. animals-full is Animalia at `>= 6`.

### The slider is the same rule, restated as a count

Because every smaller tree is a subset of the bigger, `build_animals_full.py`
writes each leaf's sitelinks as its `fame` and the tree ships once. Cutting it
to the N most famous leaves (fame descending, then name) is the scrape at the
threshold the Nth leaf sits at. Measured on animals-full:

| N | fewest sitelinks | nodes |
|---:|---:|---:|
| 500 | 64 | 1,692 |
| 1,000 | 49 | 2,795 |
| 2,000 | 38 | 4,749 |
| 5,000 | 28 | 9,561 |
| 10,000 | 23 | 16,613 |
| 20,000 | 15 | 29,605 |
| 41,153 | 6 | 57,616 |

One difference from a real scrape at that threshold, documented rather than
fixed: display names depend on the species set (a *group word* is one at least
five species' names end in, `scraper.display_names`), so a cut tree can name a
few species differently from a scrape at its threshold. The cut tree is the
honest one to play; its names come from the full build.

### What a size costs to download (Oct 2026 build)

Popup text is split by the stop at which a node enters (`info-<n>.json`;
`build_animals_full.py` has the rule).

| File | Entries | Size | gzipped |
|---|---:|---:|---:|
| `tree.json` | 57,616 nodes | 6.4MB | 0.93MB |
| `info-500.json` | 1,661 | 2.1MB | 0.57MB |
| `info-1000.json` | 1,081 | 1.2MB | 0.32MB |
| `info-2000.json` | 1,900 | 1.9MB | 0.50MB |
| `info-5000.json` | 4,743 | 4.1MB | 1.03MB |
| `info-10000.json` | 6,988 | 5.3MB | 1.20MB |
| `info-20000.json` | 12,830 | 9.0MB | 1.91MB |
| `info-41153.json` | 25,136 | 15.6MB | 3.23MB |

So the default, 2,000, needs the tree and the first three tiers: 2.3MB
gzipped, against 9.7MB for the tree and every tier. The text it needs is 16%
of the text (the plan guessed 8%). The first tier is dense for its size
because it carries the internal taxa: a node enters with its most famous
leaf, and the famous leaves are spread across the whole tree. 3,309 nodes
have no text at all (a fetch that found nothing) and are in no tier.

TaxoQuiz's Full kept a 7.5MB tree (1.2MB gzipped) and 45.6MB of text. The
tree is smaller here because Q-IDs and the second copy of each binomial stay
in the staging tree, and the text because Wikipedia's analytics tag
(`?utm_source=…`) is cut from every picture URL.

## 2. The bug this uncovered: the threshold did nothing

TaxoQuiz's `main()` loaded the species cache and passed it to `build_tree`
**unfiltered**, so once a cache existed the threshold had no effect in either
direction: 10, 30 and 50 all built the same 41,140 species. Lowering it fetched
nothing (the cache short-circuited), and raising it filtered nothing, though
the README described both as features. `at_threshold()` narrows the cache
before the tree is built, and is regression-tested.

## 3. Ancestors are only ~44% covered

The guess was that obscure species mostly hang off genera already held, making
stage 2 nearly free. On a 2,000-species sample of the `[6,10)` band: 1,083
distinct parents, 478 (44%) cached, 605 to fetch, about **0.30 new ancestor
nodes per new species**. `fetch_all_ancestors(species, known=)` fetches only
the lineages new species introduce, instead of being skipped whenever the
ancestors cache existed.

## 4. SPARQL page size: bigger is better, up to a cliff

Over the `[6,10)` band:

| LIMIT | secs | rows/s |
|---:|---:|---:|
| 1,000 | 26.8 | 37 |
| 2,500 | 11.0 | 227 |
| 5,000 | 29.4 | 170 |
| **10,000** | **15.8** | **632** |
| 20,000 | — | 502 Bad Gateway |

Noisy in the middle; the ends are the signal. `--page-size` is a flag.

## 5. Wikipedia is the long pole, and the first measurement was wrong

The first profile of the popup-text scrape showed 8 workers 25× faster. It
re-fetched the batches the serial arm had just pulled, so it was reading
Wikipedia's warm cache. With distinct, obscure titles per batch:

| Mode | nodes/s | vs serial |
|---|---:|---:|
| serial (`DELAY=0.5`) | 20.5 | 1.0× |
| ×2 | 76.2 | 3.7× |
| **×4** | **116.1** | **5.7×** |
| ×8 | 107.7 | 5.3× |

**And concurrency was not adopted**, because seeding made it unnecessary:
`taxon_info.json` is keyed by node name and the scraper fetches only names it
lacks, so copying the previous file across (`seed_taxon_info.py`) leaves only
the new nodes, about 15,000 rather than 42,000, roughly 12 minutes serially.
Threads would save ten minutes on a job run once, at the price of new code and
a worse-behaved client against a donated API. The measurement that changes
your mind is worth as much as the one that confirms it.

The seeder's guard: an entry whose Q-ID disagrees with the new tree's node of
that name is dropped and re-fetched, since `make_names_unique` can qualify a
name (`Lepus (Lepus)`) differently as the tree grows. Seeding the Sep 2026
rebuild from its predecessor left 569 of 57,051 nodes to fetch; seeding
animals-full from TaxoQuiz's file kept 57,616 with no Q-ID mismatch.

## 6. Stage 1 really does resume

The cache was once written only after the whole paged fetch returned, so a run
that died on its last page saved nothing, though the README promised resume.
`fetch_species` takes a `checkpoint` callback, `main()` writes the merged cache
after every page, and `ORDER BY ?species` keeps each saved prefix stable.

## 7. The bug that mattered most: taxa with no English label

`fetch_nodes_batch` asked for an English label as a **required** clause.
*Dinosauriformes* (Q2740164) has a scientific name and a parent and no English
label, so it returned no row, and skipping one node detaches everything below
it. `build_tree` wrapped the orphans in a synthetic `Life` root and reported no
error. Dinosauriformes alone cost 10,625 species: every bird.

| Build | Animalia species | Disconnected roots |
|---|---:|---:|
| as first built | 26,434 | 910 |
| + self-healing ancestor walk | 30,200 | 174 |
| **+ optional label** | **41,181** | **3** |

Rebuilt at the old threshold of 10 with the fixes: 34,358 species against the
18,421 shipped. So of the jump to 41,152, **+15,937 was the bug and +6,794 the
lower threshold**: the earlier dataset was missing 46% of Animalia and nothing
in it looked wrong.

Two lessons: **a required clause in a batch query is a silent filter**, and
**watch the orphan count** (`build_tree` prints "N disconnected roots"; it
went 133 → 910 and nothing treated that as a failure).

## 8. Where the popup scrape's time goes

Predicted 24 minutes, took **63**: the profile in §5 measured only the
Wikipedia summary call. Per 50-node chunk, 6.4s: Wikidata Q-IDs to titles 1.0s,
Wikipedia round 0 (3 requests) 3.0s, **fallback rounds 1–3 (~3 requests)
~2.4s**, checkpoint 0.32s. The fallback rounds are half the requests for a
small share of the work, since the miss rate is ~10% at threshold 6.

**Open improvement:** rounds 1–3 carry well under 20 titles between them and
could be one request, roughly 40% off the runtime. Checkpointing looks like
the suspect (a 44.5MB file rewritten every 50 nodes) and is 5%.

## 9. What shipped as TaxoQuiz Full, and what animals-full is

TaxoQuiz's `wikidata-2026-09-sl6`, 4 Sep 2026: 41,152 species, 56,980 nodes,
max depth 82; 2,489 species (6%) and 610 internal taxa without text; 31,566
species (77%) with a picture.

animals-full is its successor, `wikidata-parents-fixed` (Sep–Oct 2026: every
parent kept, synonyms merged, names chosen; see `docs/animals-full.md`):
**41,153 species, 57,616 nodes, max depth 85**.
