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
| `build_animals.py` | `datasets/animals` | TaxoQuiz's committed example (`--taxoquiz ../TaxoQuiz`) |

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
- **Pass-throughs.** A group with one child is never anyone's LCA. Splice it
  out unless it is worth reading on its own (a language family with one member
  still says something).
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
