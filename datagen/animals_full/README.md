# datagen/animals_full — the Wikidata animals pipeline

TaxoQuiz's datagen, ported in Oct 2026 (TaxoQuiz's `datagen/README.md` and
`data/README.md`, edited). It builds the tree behind `datasets/animals`:
every animal species at least six Wikipedias cover, 41,153 of them, hung on
Wikidata's tree of life. It is animal-specific (Linnaean ranks, binomials, the
Catalogue of Life), which is why it lives in its own directory rather than as
one `build_*.py`.

`build_animals_full.py`, one level up, turns its output into the dataset.
**Nothing here needs running to build that**: a fresh work directory is
seeded from a TaxoQuiz checkout's caches and last tree. Run the pipeline to
refresh the data.

What changed in the port is in `taxo.py`'s docstring: the scripts took paths,
tree helpers and ranks from TaxoQuiz's package and now take them from that
shim (ranks on TreeQuiz's ladder), and `net.py` stands in for `requests`, so
nothing here needs more than the standard library. Each script's own docstring
has its decisions. History of what went wrong and why the checks exist:
`docs/animals-full.md`. Timings and sizes: `docs/scaling.md`. Fixing Wikidata:
`docs/upstream.md`.

## Running it

From the repo root, in this order; each reads the one before. Every step is
resumable and every write atomic.

```bash
# 0. Nothing: build_animals_full.py seeds the work directory from ../TaxoQuiz
python3 datagen/build_animals_full.py --taxoquiz ../TaxoQuiz

# To refresh from Wikidata instead (network; the popup text alone took 63 minutes once)
python3 datagen/animals_full/scraper.py --min-sitelinks 6 --plan   # say what it would fetch
python3 datagen/animals_full/scraper.py --min-sitelinks 6          # -> _raw/wikidata-tree-raw.json
python3 datagen/animals_full/extract_game_tree.py --dataset next   # -> next/tree.json
python3 datagen/animals_full/seed_taxon_info.py --from game --to next
ANIMALS_FULL_DATASET=next python3 datagen/animals_full/scrape_taxon_info.py   # only what is new
python3 datagen/animals_full/validate_dataset.py --dataset next
python3 datagen/build_animals_full.py --dataset next               # -> datasets/animals/

# Then, if it is to be published (asks nothing without --yes; the owner's call)
python3 datagen/publish_release.py animals
```

Build the next tree beside the current one (`--dataset next`) and switch when
happy: `extract_game_tree.py` refuses to overwrite a staging tree without
`--force`, so there is never a moment when the working data is gone and the new
data is not ready.

The scraper's stage 3 (the raw tree) needs the network even with warm caches:
one query resolves every rank's label, and `display_names` asks for English
Wikipedia titles. So the cached raw tree can lag the last staging tree. The one
seeded from TaxoQuiz is from 13 Sep 2026, before the October passes (names,
synonyms, parent tie-breaks); extracting it gives 41,180 species, where the
staging tree TaxoQuiz built from a fresher one has 41,153.

## Where things are

Everything generated is under `datagen/_cache/animals-full/` (gitignored, and
nothing reads it at runtime):

| Path | What it is | Made by |
|---|---|---|
| `_raw/wikidata-species.json` | Q-ID → `{common_name, common_names, label, scientific_name, parent, parents, sitelinks, synonym_links}`, 63k species of all life at ≥6. **The only place `sitelinks` survives**, so it is also where every leaf's `fame` comes from | `scraper.py` stage 1 |
| `_raw/wikidata-ancestors.json` | Q-ID → ancestor metadata, filled while walking parent taxa up | stage 2 |
| `_raw/wikidata-tree-raw.json` | Those two as one nested tree rooted at Life, ~118MB | stage 3, offline but for ranks and titles |
| `_raw/col-names.json` | The Catalogue of Life's answers, by name | `authorities.py` |
| `_raw/synonym-report.json` | Every synonym link and the authority's verdict | `scraper.py`, for `upstream_check.py` |
| `<name>/tree.json` | A **staging tree** in TaxoQuiz's game shape; `game` by default | `extract_game_tree.py` |
| `<name>/taxon_info.json` | Wikipedia text and picture per node of that tree, keyed by name | `scrape_taxon_info.py` |

`$ANIMALS_FULL_DIR` moves the whole directory and `$ANIMALS_FULL_DATASET`
picks a staging tree. The tests point the first at a tmp dir, so they never
see yours.

Committed here: the scripts, `audit_template.html`, and
`upstream_leads.json`, the ledger of upstream leads, which holds human
decisions and cannot be regenerated.

### A larger threshold costs nothing; a smaller one costs the band

A species' sitelink count does not depend on the query, so the cache at one
threshold is a strict subset of any lower one. Raising `--min-sitelinks`
narrows the cache offline (`at_threshold`); lowering it fetches only the band
between (`fetch_plan`). `wikidata-ancestors.json` is seeded into the walk
rather than replacing it, so new species fetch only the lineages they add,
about 0.30 ancestors each. The size slider rests on the same fact.

### Raw tree, staging tree, dataset

Three shapes, and the raw one crashes anything that expects another:

| | `_raw/wikidata-tree-raw.json` | `<name>/tree.json` (staging) | `datasets/animals/tree.json` |
|---|---|---|---|
| root | Life | Animalia | Animalia |
| a leaf's `name` | the English name, "Gabon Coucal" | the binomial, *Centropus anselli* | the binomial |
| the English name | `name` | `common_name` | `label` |
| a clade's English label | `name` ("mammal") | `common_name` | in `aliases` |
| `qid` | yes | yes | no |
| `fame` | no | no | every leaf |
| names unique | no, ~60 collisions | yes, enforced | yes |

## Why `extract_game_tree.py` exists

Raw output is not playable, for three reasons that fail quietly:

1. **Wrong root.** It covers all life; the game wants a kingdom.
2. **Inverted schema, at every node.** Wikidata's English label for a famous
   clade is the vernacular (Q7377 is "mammal"), so inverting only the leaves
   left the best-known internal nodes as the only ones not in Latin.
3. **Names are not unique.** ~1,100 duplicate common names ("Cichlid" covers
   38 species) and ~60 duplicate node names: real homonyms (*Gnathostomata* is
   a vertebrate clade and a sea-urchin superfamily), genera labelled with a
   binomial, genus/subgenus pairs. Indexes key on the name, so each collision
   silently corrupts play.

It also drops taxa with no species under them (a candidate parent that lost
its child, a genus none of whose species reached the threshold) and **refuses
to write** if a duplicate survives or the shape and warmth checks fail.

## Checking

`validate_dataset.py` holds a staging tree to what TreeQuiz's validator cannot
see there: every leaf a species, common names unique ignoring case. Warmth and
the orderings are the same checks on the same ladder, with the orderings read
from the animals manifest. `write_dataset` runs TreeQuiz's validator again
on the converted tree and refuses one that fails.

`audit_dataset.py` fails nothing: it lists what would look wrong in explore,
with where the fix belongs (`--html` for a filterable report).
`upstream_check.py` confirms the strongest leads on live Wikidata and keeps
them in the ledger; it never edits anything. See `docs/upstream.md`.

## Ranks

Every rank Q-ID is resolved from Wikidata in one batched query at build time.
A hand-written shortcut table once sat in front of it, and 15 of its 23
entries were wrong. Wikidata's ranks are still wrong in places, so the ladder
believes a rank only where the tree agrees with it; the share rejected is the
number to watch (`docs/animals-full.md`).
