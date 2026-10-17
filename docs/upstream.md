# Fixing what we find, upstream

*From TaxoQuiz's `datagen/UPSTREAM.md` (Oct 2026). The loop below runs on
animals-full today; phase 6 of `taxoquiz-merge-plan.md` makes the ledger
per-dataset (`datagen/upstream/<id>.json`) and seeds it with the leads the
other builders found by hand.*

TreeQuiz's Wikidata trees are built from Wikidata and Wikipedia, so reading
41,000 species through a game turns up their mistakes. This file holds the
rules for acting on them and describes the loop that keeps track.

## Wikidata and Wikipedia are different things

Which one a mistake lives in decides who fixes it and how.

| | **Wikidata** (wikidata.org) | **Wikipedia** (en.wikipedia.org) |
|---|---|---|
| What it is | A database of facts, one *item* per thing, each with an ID like Q140 | An encyclopedia of articles, written as prose |
| One entry looks like | Q140: taxon name *Panthera leo*, rank species, parent taxon Q127960, English common name "lion", image "Lion waiting in Namibia.jpg" | The article "Lion": paragraphs, an infobox, references |
| Languages | One item serves every language | Each language is a separate wiki |
| How they connect | An item lists its articles in each Wikipedia ("sitelinks") | An article belongs to one item |
| Edited by | Statements, one at a time, each optionally referenced | Text, with talk pages and stricter norms |
| What animals-full takes | **The tree**: which species exist, their names, ranks, parents, common names, the replacement photo (P18), and the sitelink count that is each leaf's `fame` | **The popup**: the summary text and the infobox picture |

So a wrong name, a wrong parent, a species in the tree twice, or "Snake" as a
common name is **Wikidata**. A popup describing the wrong animal, or a range
map where a photo should be, is **Wikipedia**, though the wrong-animal case is
often a Wikidata *sitelink* pointing at the wrong article. Fixing an item on
Wikidata changes it for every language's Wikipedia at once, which is why it is
worth doing and why it deserves care.

A third kind of source sits behind both: **taxonomic authorities**, the
databases specialists keep for one group (the Reptile Database, WoRMS, the
Mammal Diversity Database, Amphibian Species of the World, the bird lists).
The **Catalogue of Life** assembles them and says which authority each answer
came from, which is how `datagen/animals_full/authorities.py` asks them. Where
Wikidata is ambiguous, the group's authority is the closest thing to a source
of truth. It can lag too, so it is a second opinion, never the only one.

## Rules

**Slowly, by hand, one edit at a time.** Nothing here edits anything. Every
change is made by a person, under their own account, after reading the item,
its references and its history. Wikidata's bot policy expects that for
anything beyond a small manual batch, and a wrong edit costs other editors'
time and the project's goodwill. The aim is edits that never need reverting.

1. **Start with reverts.** A bad value introduced recently, by a temporary or
   new account, over one that stood for years, is the safest edit there is.
2. **Then single-statement fixes the item itself proves**: its own label,
   article title and species agree on the right value.
3. **Never remove a sourced statement** without reading the source.
4. **A pattern is a conversation, not a batch.** Where one cause explains
   hundreds of hits, raise it with WikiProject Taxonomy (Wikidata) or
   WikiProject Tree of Life (Wikipedia) before touching any of them.
5. **Wikidata before Wikipedia.** No Wikipedia edits until the Wikidata side
   has gone well for a while.
6. **Record every edit**, and look again a week later to see whether it stood.

## The loop

```bash
# 1. Find: what looks odd, offline, from our own data
python3 datagen/animals_full/audit_dataset.py --html audit.html

# 2. Confirm: re-ask live Wikidata, gather evidence, update the ledger
#    (--photos also asks Commons about map-only species; ~25 minutes)
python3 datagen/animals_full/upstream_check.py --out leads.md

# 3. Fix by hand on wikidata.org, then record it
python3 datagen/animals_full/upstream_check.py --mark bad-species-name:Q1956228 edited --note "<diff link>"

# 4. A later run of step 2 sees the fix live and marks the lead resolved

# 5. Pull fixes back into the caches, then rebuild as usual
python3 datagen/animals_full/scraper.py --min-sitelinks 6 --refresh-ledger
```

`datagen/animals_full/upstream_leads.json` is the ledger and is committed: the
one thing here that cannot be regenerated, since it holds human decisions and
the history of what was fixed when. A lead is `confirmed`, `edited`,
`dismissed` (judged not an error, never raised again) or `resolved` (no longer
reproduces, whoever fixed it). A run never overwrites a human status or note,
and resolves a lead only when it actually re-asked Wikidata about that item.
Resolved leads reopen if the error returns, which is how repeated vandalism
shows itself.

Step 5 exists because the caches are never re-asked about anything they hold.
That keeps rebuilds cheap, and means a vandalised name, once scraped, would
stay in the game after Wikidata had been put right.

## Kinds of lead

| Kind | What it is | Found first |
|---|---|---|
| `binomial-on-higher-taxon` | A genus's taxon name (P225) is a binomial | *Hippocamelus*, renamed "Six seven" and then "Hippocamelus bisilcus" by a temporary account in May 2026 |
| `bad-species-name` | A species' taxon name is not a binomial | *Oreochromis lidole*, renamed "something about fish" by an IP in March 2023; the emperor newt's name has a non-breaking space from a 2013 bot import |
| `genus-unlike-its-species` | A genus's taxon name differs from the word all its species start with, and its own label or title is that word | *Sepia*, renamed "Sapia" by a temporary account in May 2026, over 34 cuttlefish |
| `preferred-parent-skips-a-level` (review) | A taxon's preferred parent is broader than another of its parents, which lies beneath it; tools reading "truthy" values (ours included) skip the level between | *Diprotodontia* prefers Mammalia over Marsupialia (since 2017), so kangaroos sit directly under the class; 25 in animals-full |
| `photo-on-commons` (review) | A species shown only as a range map, whose item has no image (P18), while Commons has a photograph that depicts it (P180) or sits in its category. A gap, not an error. Opt-in, `--photos` | 154, Oct 2026 |
| `disputed-synonym-link` (review) | Wikidata calls species B species A's synonym or original combination, and the group's authority holds them distinct | *Calomys lepidus*, a vesper mouse, claiming the woodrat *Neotoma lepida*; 31 in the game's species |

A `confirmed` kind must be provable from the item itself. A `review` kind may
rest on an outside authority's word, and says so in its evidence, with links to
that authority's page. If finding it needs taxonomic judgement beyond that, it
is an audit check and stays there.

The Diprotodontia lead is visible in the game: a kangaroo meets a bat at the
class, level with the platypus. animals-full's manifest therefore tests the
bat chain with the Tasmanian devil, whose order Wikidata files correctly.

## Patterns, not edits

**Group words as common names** (`group-noun-common-name` in the ledger).
About 1,000 species carry a bare group word ("Snake", "Triggerfish",
"Cichlid") among their English names; 774 cite the IUCN Red List and 74 ARKive,
both bulk imports, so the sources really say it, and some are genuine names
(the British moths "Chestnut" and "Peacock"). The game no longer shows these
where a better name exists (`scraper.display_names`). Upstream, the useful step
is a note on WikiProject Taxonomy with these counts, not removals.

## Cross-referencing: two sources before the game changes

Where Wikidata says one species item is another under an older name (taxon
synonym P1420, original combination P1403, basionym P566, replaced synonym
P694), the build asks the Catalogue of Life about both. On the 83 such links
between species in the tree (Oct 2026):

| Outcome | Links | What happens |
|---|---:|---|
| Both agree one is the other's synonym | 27 | The synonym leaves the game; its English names join the accepted species |
| The authority holds them distinct, often in different families | 30 | Nothing in the game; most are wrong links on Wikidata |
| Unsettled: subgenus disputes, unknown names, the authority behind | 26 | Nothing. Three are birds where COL's source (ITIS) lags the bird lists |

The first count had 32 distinct. Two were names COL does not hold: its match
answers those with the nearest higher taxon, flagged `higherrank`, and the
genus was read as the species' accepted name. `authorities.py` treats that as
"unknown", and the two leads are dismissed with the reason.

The game changes only when two independent sources agree. The GBIF backbone,
tried first, still lists the Nilgiri tahr under *Hemitragus*, two decades after
the split.

## Other leads, not yet worked

From `audit_dataset.py`, Oct 2026. Each needs taxonomic judgement, so none is
in the ledger.

| Lead | Hits | Note |
|---|---:|---|
| No photo anywhere | 1,663 | Wikipedia's picture is a range map and the item has no image; 154 have a Commons photo and are `photo-on-commons` leads |
| Binomial filed under another genus | 156–162 | 44 are old names whose current name is in the genus they hang from (*Dasyatis americana* under *Hypanus*); 83 COL accepts as named; 29 point elsewhere again. Taxonomic questions, not edits |
| Same animal as two items | 126 | Wikidata keeps one item per *name* on purpose; the fix is marking the old name a synonym |
| Rank contradicts the tree | 233 | |
| Taxon whose article is about another rank | 125 | Often an obsolete genus whose title redirects to its one species |

Seen while porting (Oct 2026), not yet checked: Wikidata files *Nardoa rosea*,
the rose sea star (Q2694145), under the sponges, so animals-full has three
"sponges" and one is a starfish. Its parent is *Nardoa* Q15868408, filed in
the calcareous sponge family Leucascidae: most likely a sponge homonym of the
sea-star genus, and the species' P171 points at the wrong one.

**Wrong "depicts" statements on Commons.** The photo scan trusts a file that
says it depicts (P180) the species, and that is a claim like any other: four
photos of a cemetery chapel in Grefrath say they show the Venezuelan
flowerpiercer, and two of red ruffed lemurs say they show *Lepilemur
grewcockorum*. A depicts file whose name does not mention the animal is now
offered with a warning. The fix is on Commons: remove the statement from the
file's structured data. Small, provable from the photo, and a good first edit.

Every account behind a confirmed vandal edit so far made that edit and nothing
else (checked Oct 2026 with `list=usercontribs`), so there was no spree to
follow.

## Edits made

| Date | Lead | Diff | Stood a week later? |
|---|---|---|---|
| | | | |
