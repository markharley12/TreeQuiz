# TreeQuiz

Find the secret leaf of a tree. Every guess shows where it branches off from the
answer, and the nearer that branch point, the warmer the colour.

TreeQuiz is [TaxoQuiz](https://github.com/markharley12/TaxoQuiz) with the
biology taken out. TaxoQuiz's game, explore mode, colour scale, seeds, hints
and phone layout all work on *any* tree. A dataset brings the tree and a short
manifest saying what its leaves are called, and the engine knows nothing else
about it.

![The front page](docs/images/start.png)

## The trees

| Tree | Leaves | Depth | Built from | Ranks |
|---|---:|---:|---|---|
| **Maths** | 517 fields | 5 | [MSC2020](https://msc2020.org), the Mathematics Subject Classification, with a curated branch/area layer above its 63 subjects | ladder: branch → area → subject → section |
| **Languages** | 415 languages | 14 | [Glottolog 5.3](https://glottolog.org)'s family tree, languages chosen by how many Wikipedias cover them | none: placed by the tree's shape alone |
| **Instruments** | 428 instruments | 9 | The [Hornbostel–Sachs](https://en.wikipedia.org/wiki/Hornbostel%E2%80%93Sachs) classification, by what vibrates; instruments and their numbers from [Wikidata](https://www.wikidata.org/wiki/Property:P1762) | none |
| **Animals** | 530 species | 21 | TaxoQuiz's hand-curated taxonomy | the Linnaean ladder |

Each tree was picked to test something different. Maths is shallow with clean
ranks. Languages has no ranks at all, so warmth comes from the tree's shape
alone. Instruments is a classification whose codes *are* the tree: a violin is
321.322-71 and a guitar 321.322-5, so they share 321.322, necked box lutes.
Animals is TaxoQuiz's own data, and its game comes back out unchanged.

![A round of Maths](docs/images/game.png)

## How a round works

You guess a leaf. The game draws the guess's lineage and colours it by its
**lowest common ancestor** (LCA) with the secret: share only the root and it is
red, share the secret's immediate group and it is nearly green. A dashed `???`
node shows *which branch* the answer is on, never how deep.

- **Daily** is the same round for everyone today; **Practice** is a random one.
  Every round has a seed (`YCW7-2ZXMAA`) and a share link (`?d=maths&seed=…`).
  A seed's first four characters fingerprint its tree, so a seed pasted on the
  wrong tree is recognised and offered on the right one.
- **Hints** reveal one more node of the answer's lineage, and double your score.
- **Bulk guessing** opens once you have reached a narrow enough group. Type a
  word, and every leaf in that group with that word in its name is guessed at
  once, each one counted.
- **Explore** has no secret: open the tree anywhere and read it. Every node has
  a popup. For maths that's its MSC topics; for animals and languages it's the
  Wikipedia summary.
- Each tree keeps its own round, so switching tree loses nothing.

## Playing

```bash
cd frontend && npm install && npm run dev      # http://localhost:5173
```

The app needs no server: the engine runs in the browser, and the build is
static files (`npm run build`, then serve `frontend/dist`). The dev server finds
datasets when it starts, so restart it after adding one. In a terminal:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[test]"
.venv/bin/treequiz list
.venv/bin/treequiz play languages
.venv/bin/treequiz explore maths
```

## Adding a tree

This is what the repo is for. A dataset is a directory:

```
datasets/<id>/manifest.json   what the tree is about — written by hand
datasets/<id>/tree.json       the tree — written by a builder or the importer
datasets/<id>/info.json       popup text per node — optional
```

The app finds every directory under `datasets/` at build time, so adding one
needs no frontend change.

**The quick way**: write the tree as an indented outline, or export a
`name,parent` CSV from a spreadsheet, and import it:

```
Programming languages
  Lisp family | Family
    Common Lisp | Language | CL
    Scheme | Language
    Clojure | Language
  ML family | Family
    OCaml | Language
    Standard ML | Language | SML
```

```bash
.venv/bin/python datagen/import_tree.py langs.txt --id proglangs --init
```

`--init` writes a starter manifest to fill in. **The thorough way** is a builder
script that downloads a source and shapes it, like `datagen/build_maths.py`.
See [`datagen/README.md`](datagen/README.md) for both, and for the mistakes
the validator exists to catch.

### The manifest

```json
{
  "title": "Fields of mathematics",
  "short_title": "Maths",
  "prompt": "Guess the secret field of mathematics by where it sits in the subject.",
  "blurb": "About 500 research fields, from graph theory to general relativity…",
  "noun": "field",
  "noun_plural": "fields",
  "ladder": { "levels": { "branch": 1, "area": 2, "subject": 3, "section": 4 }, "top": 4 },
  "bulk_unlock": 0.5,
  "info_source": "MSC2020",
  "long_labels": true,
  "order": 1,
  "sources": [{ "name": "MSC2020", "url": "https://msc2020.org", "licence": "CC BY-NC-SA 4.0" }],
  "checks": { "closer": [{ "to": "05Cxx", "order": ["05Axx", "03Exx", "11Axx"] }] }
}
```

Only `title` is required. `checks.closer` lists relationships nobody disputes,
as orderings: graph theory is closer to enumerative combinatorics than to set
theory, and closer to set theory than to number theory. The validator fails a
tree that breaks one. That is how TaxoQuiz caught a tree that was internally
consistent and still wrong.

### Tree nodes

```json
{ "name": "05Cxx", "label": "Graph theory", "rank": "Section", "aliases": ["05C"] }
```

`name` is unique and is the key; `label` is what's shown and, for a leaf, what's
guessed (default: the name); `aliases` are other things a player might type.
Leaf labels must be unique ignoring case.

## How warmth works

A node's **warmth** is how specific it is, from 0 to 1. A guess scores the
warmth of its LCA with the secret.

- **The root is 0 and every leaf is 1**, whatever their ranks say: everything
  shares the root, and finding the leaf is winning.
- **A ladder places ranked nodes.** In maths, a shared subject is worth ¾
  wherever it sits. A rank is a *claim*: one that contradicts the tree (a
  suborder containing a phylum) is not believed.
- **Everything else is interpolated** between the nearest believed ranks above
  and below, so a chain of unranked groups fans out evenly. Going deeper is
  always strictly warmer.

With no ladder at all, interpolation is all there is: a node sits at the
fraction of the way down the longest lineage beneath it. The languages tree
works this way, and every one of its 23 ordering checks passes, from
English–Scots–Frisian–German down to Arabic–Hebrew–Amharic–Hausa–Swahili.

![A round of Languages: the answer is Portuguese](docs/images/languages.png)

The answer above is Portuguese. Japanese shares only the root, Russian only
Indo-European, Italian and French narrower groups of Romance, and Spanish its
closest one. Nothing in the languages manifest says how wide a family is; the
colours come from the tree's shape alone.

![A round of Instruments: the answer is the cello](docs/images/instruments.png)

Instruments work the same way. The answer above is the cello. The tuba is an
aerophone and shares nothing with it. The piano is a chordophone too, but a
zither by Hornbostel–Sachs, so that is all it shares. The harp is a composite chordophone like
the cello, the sitar a necked lute, and the guitar a necked *box* lute like
the cello. The viola is bowed as well, so it shares the cello's closest group.

## Layout

```
src/treequiz/   the engine, in Python: the reference implementation, CLI and validator
frontend/       the app: React + MUI + react-d3-tree, with the engine ported to TypeScript
datasets/       one directory per tree; committed
datagen/        builders and the importer; downloads go to datagen/_cache/ (ignored)
tests/          the Python suite, and the generator of the conformance file
```

**The engine runs twice**, in Python and TypeScript. `tests/conformance.py`
writes Python's answers to a fixed set of questions, over every shipped
dataset, into `frontend/src/engine/conformance.json`. Both suites check it, and
compare numbers exactly. Change the Python, regenerate it, then port until
`npm test` passes.

```bash
.venv/bin/python -m pytest -q                  # Python: engine, datasets, builders, CLI
.venv/bin/python tests/conformance.py          # after any engine or dataset change
cd frontend && npm test                        # TypeScript: engine conformance, app, layout
```

## Licences

The code is TreeQuiz's. The data carries its sources' licences, and each
manifest says so; the app shows the attribution on the front page and in every
popup.

- **Maths**: MSC2020 by zbMATH Open and Mathematical Reviews,
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). The
  branches and areas above the subjects are TreeQuiz's own grouping. The
  dataset is redistributed here under the same terms, *non-commercially*.
- **Languages**: Glottolog 5.3, Hammarström, Forkel, Haspelmath & Bank (2026),
  Max Planck Institute for Evolutionary Anthropology,
  [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  doi:[10.5281/zenodo.15525265](https://doi.org/10.5281/zenodo.15525265).
  Choice of languages from [Wikidata](https://www.wikidata.org) (CC0).
- **Instruments**: instruments and their Hornbostel–Sachs numbers from
  [Wikidata](https://www.wikidata.org) (CC0). Three numbers are corrected by
  hand. Class names come from English Wikipedia's *Hornbostel–Sachs* article
  and its four lists by number, after von Hornbostel & Sachs (1914), and are
  shortened where a name only reads under its parent. The electrophone class
  names are TreeQuiz's own, following the 2011 MIMO revision that Wikidata's
  numbers use.
- **Animals**: the taxonomy is TaxoQuiz's hand-curated tree.
- **Popup text** for languages, instruments and animals is from English Wikipedia,
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/); every entry
  links its article. Images are linked from Wikimedia Commons and carry their
  own licences.
