# animals-full: how the data went wrong, and what checks it now

*The tree ships as `animals` since 17 Oct 2026; it was `animals-full`
beside TaxoQuiz's curated 530 until then, and this history keeps that name.*

*TaxoQuiz's history of its Wikidata tree (Aug–Oct 2026), from the "Dataset",
"Validating a dataset" and "Auditing a dataset" sections of its CLAUDE.md,
edited to TreeQuiz's names. The display decisions those sections also held
(colour by rank, believed ranks, the strict floor) came across with the engine
and are documented in `src/treequiz/ladder.py`; they are not repeated here.
How to run the pipeline is in `datagen/animals_full/README.md`, and its timings
in `docs/scaling.md`.*

## The one habit behind most of it

Taking **the first available answer instead of the best one, and never checking
the result against anything outside itself.** A hand-written rank table
answered before the query could; a fixture recorded only the ranks its
generator knew; the scraper kept whichever parent row arrived first. Every one
passed a test suite that checked code against fixtures it wrote, because the
errors were in the data. The remedy each time was the same: check the claim
against evidence, and test the shipped tree against the world (the manifest's
`checks.closer`, which `write_dataset` enforces).

## Ranks

- **A hand-written rank table, 15 of 23 entries wrong** (fixed Sep 2026).
  `RANK_LABELS` sat in front of the rank lookup as a shortcut, so its answers
  always won: `Q1054074` ("superorder") is a Fiat 600 Multipla, `Q2361108`
  ("cohort") a place in Sweden. 355 beetle superfamilies were `Subkingdom`;
  the share of edges whose child out-ranked its parent fell from 2.65% to
  0.13% once every rank was asked of Wikidata, in one batched query
  (`fetch_rank_labels`, ~53 ranks whatever the size).
- **Ranks resolve themselves** (Aug 2026). An unrecognised rank used to fall
  through as a raw Q-ID (1,609 nodes, `tribe` among them); two more had a
  value-node hash, from parsing a URI with `split("/")` rather than
  `extract_qid`. A rank with no English label is `clade`.
- **Ranks that mean two things are off the ladder.** `division`, `section`,
  `series` and their sub- forms are botanical ranks near phylum and genus *and*
  zoological ones below class: *Ctenosquamata* is a section of 4,482 fish
  nodes. They are unranked and the tree places them. The animals ladder in both
  manifests already leaves them out.
- **A rank is a claim; the tree is the evidence.** The share of rank claims
  the ladder rejects is the early-warning number: 0% for the curated 530,
  0.28–0.41% for the rebuilt Full (1.44% counting only internal nodes, as
  TreeQuiz's validator does), 6.5% for the scrape from before the table was
  removed, which was a dataset to rebuild, not play.
- **Rank casing** (`extract_game_tree.title_rank`): capitalise the first
  letter only, "Species group" not "Species Group".

## Names

- **Wikidata labels a famous clade in English, and that is not its name.**
  Q7377 is "mammal", Q5113 "bird", Q729, the root, "animal". The scientific
  name is P225. The raw tree keeps both (English in `name`, P225 in
  `scientific_name`) and `extract_game_tree.py` inverts every node, not only
  the leaves; the English survives as `common_name`, which
  `build_animals_full.py` makes an alias, so explore finds Aves by "bird". An
  ancestor cache from before the fix cannot be repaired by inspection, so
  entries without `sci` are refetched.
- **The Komodo dragon was called "Ora".** A quarter of species have several
  English names (P1843), and the first row won. Every name and the English
  label are kept, and `common_name_of` picks the label when P1843 repeats it,
  else the first alphabetically, so a rebuild cannot flip between them.
- **Group words** (`display_names`, Oct 2026). A bare noun at least five
  species' names end in ("Snake") loses to a name that narrows it ("Sumatra
  Etheridge Snake"). Narrowing every bare word was tried and swapped the elk
  for a regional subset. With a group word the only name, the species'
  English Wikipedia title decides: equal, it stays ("Cat"); an English title
  replaces it ("Hornet" → "European hornet"); otherwise the binomial is
  appended ("Chameleon (Furcifer nicosiai)"). 186 names changed.
- **A label its article agrees with.** Where the label and the enwiki title
  are one name, two sources agree and the label wins, unless it is a binomial
  or another species' name. *Pagrus auratus* had shown as "Cockney", first of
  fourteen fishmonger's names; 951 names changed.
- **Names unique ignoring case.** 118 pairs like "Pacific Lamprey" and
  "Pacific lamprey", mostly one animal filed twice under synonym binomials.
  Colliding names get the binomial appended, then a number (two items share
  *Colluricincla tenebrosa*).
- **63 real species were deleted** by `collapse_nested_duplicates`, which
  dropped a leaf repeating its parent's name; the raw tree names a species in
  English, which for a monotypic genus is often the genus's name. The
  hippopotamus, indri and addax among them. A leaf is never dropped for its
  name now.

## Parents

- **The bat chain** (fixed Sep 2026). A vampire bat scored the same against a
  wolf, a human, a kangaroo and a platypus: *Chiroptera* hung straight off
  *Mammalia*, and 106 edges skipped a full rank tier. A taxon can have several
  P171 statements (Chiroptera has eight) and the first row won. Every
  candidate is now kept (`parents`), the walk fetches all of them, and
  `choose_parents` hangs each node from the one with the **longest path to a
  root**; a descendant's path is always the longer, so no "which is narrower"
  test is needed. An old cache is repaired in place.
- **"Every candidate" means every *truthy* candidate.** `wdt:P171` sees only
  the preferred statement when one exists, and *Diprotodontia* prefers
  Mammalia, so kangaroos still meet bats at the class. Kept deliberately: a
  preferred rank is an editor's choice, and the hidden parents are often an
  older classification. Overriding it would be the rank-table mistake again.
  These are `preferred-parent-skips-a-level` leads (`docs/upstream.md`).
- **Ties go to the genus the binomial names** (Oct 2026). Equally deep
  candidates were settled by Q-ID, which hung the American mink from
  *Neovison* beside its own *Neogale*; 7 species moved.
- **A spent query answered "nothing found".** `sparql` returns no rows once
  its retries are spent, and the parent repair read that as "keep the cached
  parent, mark it done", closing 400 species off from repair after one 502.
  That query is `strict=True` and raises.

## Leaves that were not species

Keeping every parent made fake species: a candidate parent that loses its
only child to a more specific one is left childless, and the extractor stamped
`"Species"` on every leaf. The first rebuild carried **189 childless clades as
species**, *Apo-Chiroptera* among them, a bat photograph and a dead end beside
the real bats, guessable and drawable as a secret. An announced "gain of 139
species" was in fact a loss of 3, plus fakes. Three layers now:
`drop_childless_taxa` removes every leaf that was not a species in the raw tree
(210 nodes), `convert` keeps a leaf's own rank so one that slips through is
visible, and the staging validator **fails** a leaf that is not a species.

## One animal under two names

Wikidata keeps one item per *name*, so a renamed species could sit in the tree
twice (the Nilgiri tahr under *Hemitragus* and *Nilgiritragus*) and a guess of
one lost to the other. A species is dropped only when **two independent
sources agree** (`scraper.drop_synonyms`): Wikidata links it as synonym,
original combination, basionym or replaced synonym, and the Catalogue of Life
calls it a synonym of exactly that species. Of 83 links, 27 agreed. The rest
are review leads or unsettled; `docs/upstream.md` has the table.

## Popup text

- **One entry per node, species included.** Species were left out at first,
  which left the things you guess as the only nodes you could not read about.
- **Titles come from the Q-ID** (`wbgetentities`, 50 at a time, about one
  request per fifty nodes, cheaper than guessing). Where a name must be used,
  a species uses its binomial: "gazelle" fetches the genus's article,
  *Gazella gazella* redirects to "Mountain gazelle".
- **Text stranded by renames.** The file is keyed by node name, and
  `make_names_unique` qualifies a name only while it collides, so a
  re-extraction turned "Lutrogale (Lutra)" into "Lutrogale" and three popups
  went blank with their text still in the file. `rekey_by_qid` moves an entry
  onto its node's current name by Q-ID.
- **Range maps** (`replace_map_images`). ~2,080 nodes wore a range map, the
  infobox's first picture. Wikidata's P18 replaces it where it is not itself a
  map: 300 swapped, 1,783 have nothing better. Map detection is by whole words
  of the filename; substrings matched *Scartella* and *Orange_roughy*.
- **The popup names an article that is not the node's own**: under the genus
  *Lissonycteris*, "From Wikipedia's article *Angolan fruit bat*". 15% of
  Full's popups are another page, mostly harmlessly (Cervidae is "Deer").
  TaxoQuiz showed this note (`otherArticle` in its `names.ts`); TreeQuiz's
  popup does not yet.

## Smaller lessons

- **The orphan count is the cheapest alarm.** Disconnected roots went 133 →
  910 when English labels became required, and nothing failed (`docs/scaling.md`
  §7).
- **Nothing stored that the tree already determines.** TaxoQuiz once kept a
  list of taxa to fetch beside each tree, and rank inside the popup text; both
  were copies that could disagree with the tree. The popup text here carries
  neither.
- **Checked and not worth code:** 1 in 400 ancestors has several ranks
  (*Odontoceti*), already distrusted by the ladder, and no sampled species or
  ancestor has several scientific names.

## The curated 530 is not a subset of this

`datasets/animals` is TaxoQuiz's hand-built NCBI-style example, generated once
and hand-edited since (the clade layer above the phyla, Sep 2026). Nothing
rebuilds it and it is not a subtree of the Wikidata scrape, which is why it
cannot be the slider's 500 end. It is also coarser: it has no Neognathae and
no Osteichthyes, so a sparrow is as near an ostrich as a pigeon, and a salmon
as near a shark as a coelacanth. animals-full's manifest asserts both; the
curated tree is held to its own.
