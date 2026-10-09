# datagen — building trees

Everything here writes `datasets/<id>/tree.json` (and sometimes `info.json`).
The app and the engine never import it. Downloads go to `datagen/_cache/`,
which is gitignored. A rebuild reads the cached copy, and `--refresh` fetches
the source again.

| Script | Makes | Source |
|---|---|---|
| `import_tree.py` | any tree you write yourself | an indented outline or a `name,parent` CSV |
| `build_maths.py` | `datasets/maths` | MSC2020's CSV from msc2020.org |
| `build_languages.py` | `datasets/languages` | Glottolog's languoid table, Wikidata's sitelinks, Wikipedia's summaries |
| `build_instruments.py` | `datasets/instruments` | Wikidata's Hornbostel–Sachs numbers (P1762), class names from Wikipedia's Hornbostel–Sachs articles |
| `build_animals.py` | `datasets/animals` | TaxoQuiz's committed example (`--taxoquiz ../TaxoQuiz`) |
| `build_chess.py` | `datasets/chess` | Lichess's opening list (CC0), pinned to a commit; Wikipedia's leads where an opening has an article |

`san.py` replays chess moves for `build_chess.py`, which draws each position
as an SVG board. It is checked against python-chess once rather than depending
on it: every one of Lichess's 3,865 lines replays to the same position and
the same last move.

`common.py` is what they share: `write_dataset` validates a tree against its
manifest and refuses one that fails; `fetch` downloads once;
`collapse_lone_children` splices out pass-throughs. `wikipedia.py` fetches
summaries with a resumable cache.

## Making a new tree

1. **Write the manifest first**, by hand: `datasets/<id>/manifest.json`. A
   builder never writes one, so a rebuild cannot overwrite the words you chose.
   `import_tree.py --init` writes a starter to edit.
2. **Shape the tree.** Every node needs a unique `name`. Leaves need labels
   that are unique ignoring case, since a player guesses by label and the app
   capitalises it.
3. **Write orderings into `checks.closer`**: relationships nobody disputes,
   which a correct tree must reproduce. They are cheap and the best test you
   have — see below.
4. **Run it.** The builder validates before it writes. Then
   `python tests/conformance.py` and both test suites (see the main README),
   and `npm run dev` to look at it.

## The mistakes the validator exists for

All of these happened in TaxoQuiz, and every one passed its test suite, because
the tests checked the code against fixtures rather than the data against the
world.

- **A flat tree.** With 63 MSC subjects straight under "Mathematics", guessing a
  wrong subject says nothing: number theory would be exactly as far from
  algebraic geometry as from fluid mechanics. TaxoQuiz shipped Animalia →
  Phylum with nothing between, and a human scored the same against a starfish as
  against a sponge. The fix is a layer of real groups; the *check* is an
  ordering in the manifest, which a flat tree cannot pass.
- **The first answer instead of the best one.** Glottolog splits finely, and
  Wikidata hangs "Arabic", "Persian" and "Swahili" on *subgroups*, so taking
  only Glottolog's language-level entries silently dropped them. Look at what
  is missing, not only at what is there.
- **Lossy sources.** MSC's CSV is Latin-1 and turned every other character into
  `?` ("Randi? index"). `build_maths.py` repairs the ten it found and fails on
  any new one.
- **Two sources numbering differently.** Wikipedia's *Hornbostel–Sachs*
  article puts goblet drums at 211.25 and calls 423.233 "sets of slide
  trumpets". Its own *List of membranophones* has conical drums at 211.25,
  and the list of aerophones has cylindrical bore at 423.233, which is the
  numbering Wikidata files instruments by. Merged naively, an ashiko would have
  been a goblet drum. Check what a source's codes *mean* against items you
  know, not only that they parse.
- **Pass-throughs.** A group with one child is never anyone's LCA. Splice it
  out unless it is worth reading on its own (a language family with one member
  still says something).
- **Guessed titles.** Chess openings have no Wikidata link to an article, so
  `build_chess.py` guesses titles, and a guess finds the wrong page easily:
  "Chigorin Variation" is Mikhail Chigorin, "Taimanov Variation" a list of four
  openings, and "Sicilian Defence, Kan Variation" redirects to the Sicilian's
  own article. An article is believed only when its title names the opening,
  the moves in its lead agree with the opening's, and it is not the article of
  an opening above. Wikipedia's summary endpoint also stops at the move list
  that chess leads open with, so the text comes from the whole lead instead
  (`wikipedia.intros`).
- **Pseudo-groups.** A filing category is not a lineage. Glottolog's "Sign
  Language" and "Artificial Language" would score as kinship, so they are left
  out.

## Ranks, or none

A `ladder` in the manifest maps rank names to levels. Use one when a rank means
the same thing everywhere in the tree (an MSC section, a genus). Leave it out
when it doesn't: a language "family" can be two languages or six hundred. With
no ladder, every node is placed by the shape below it. Ranks still display in
the app either way.

The validator reports how many rank claims the tree contradicts. Above 5% it
fails, because that many contradictions means the ranks are wrong at the source.
