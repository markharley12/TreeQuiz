/**
 * A dataset as the engine sees it, and the walks every engine module shares.
 * Port of `treequiz/tree.py` and the shape documented in `treequiz/dataset.py`,
 * which says what each field is for.
 *
 * Lookups keyed by a name are `Map`s throughout, never plain objects: a plain
 * object answers `constructor` and `toString` from its prototype, and a name
 * that happens to be one of those would read as present.
 */

/** A node in a dataset's `tree.json`. */
export interface RawNode {
  /** Unique across the tree: the key for info and for explore. */
  name: string
  /** What is shown, and for a leaf what is guessed. Defaults to `name`. */
  label?: string
  rank?: string
  /** Other things a player might type for this node. */
  aliases?: string[]
  /** Leaves only: higher for the better known. What a cut keeps; see size.ts. */
  fame?: number
  children?: RawNode[]
}

export interface Source {
  name: string
  url: string
  licence?: string
  licence_url?: string
  note?: string
}

/** A tree that can be played cut to its best-known leaves; see size.ts. */
export interface SizesSpec {
  min: number
  default: number
  stops?: number[]
}

export interface LadderSpec {
  levels?: Record<string, number>
  top?: number
}

/** A dataset's `manifest.json`: everything the app knows about its domain. */
export interface Manifest {
  title: string
  short_title?: string
  prompt?: string
  blurb?: string
  noun?: string
  noun_plural?: string
  ladder?: LadderSpec | null
  bulk_unlock?: number
  info_source?: string
  sources?: Source[]
  /** Where the dataset sits in the picker; lower first. */
  order?: number
  /** The GitHub release whose assets are this tree's files, for a tree too
   *  big for git: the Pages workflow downloads them before building. */
  release?: string
  /** Its names are phrases, so boxes are drawn wider. */
  long_labels?: boolean
  /** Its node names are opaque keys (Wikidata or Glottolog IDs), so they are
   *  not shown beside the labels. */
  hide_names?: boolean
  /** How a collapsed chain of labels reads. Deepest first by default
   *  ("Carnivora › Mammalia"), which leads with the most specific name; root
   *  first, joined by spaces, where the labels are steps of a path — moves of
   *  a chess opening, "1.e4 1…c5 2.Nf3". */
  chain_order?: 'deepest_first' | 'root_first'
  /** A pattern taken off the start of every step but the first in a root-first
   *  chain: a chess move's "1…" says whose move it is, which the step before
   *  has already said. */
  chain_trim?: string
  /** The tree can be played at sizes from `min` to all its leaves. */
  sizes?: SizesSpec
}

/** How a dataset's chains of labels read; see `chain_order`. */
export type ChainStyle = Pick<Manifest, 'chain_order' | 'chain_trim'>

export interface Ladder {
  /** Lower-cased rank name to level. */
  levels: ReadonlyMap<string, number>
  top: number
}

export interface Dataset {
  id: string
  manifest: Manifest
  tree: RawNode
  ladder: Ladder
}

export function ladderFrom(spec: LadderSpec | null | undefined): Ladder {
  const levels = new Map<string, number>()
  for (const [k, v] of Object.entries(spec?.levels ?? {})) levels.set(k.trim().toLowerCase(), Number(v))
  const top = spec?.top !== undefined ? Number(spec.top) : levels.size ? Math.max(...levels.values()) : 1.0
  return { levels, top }
}

export function makeDataset(id: string, manifest: Manifest, tree: RawNode): Dataset {
  return { id, manifest, tree, ladder: ladderFrom(manifest.ladder) }
}

/** Python's `node.get("children") or []`: missing and empty both mean a leaf. */
export function childrenOf(node: RawNode): RawNode[] {
  return node.children ?? []
}

export function isLeaf(node: RawNode): boolean {
  return childrenOf(node).length === 0
}

export function labelOf(node: RawNode): string {
  return node.label || node.name
}

/** Every leaf, in tree order. The order is load-bearing: seeds index into it. */
export function leaves(node: RawNode): RawNode[] {
  const out: RawNode[] = []
  const walk = (n: RawNode) => {
    if (isLeaf(n)) out.push(n)
    else childrenOf(n).forEach(walk)
  }
  walk(node)
  return out
}

/** Python's `repr()` of a string, so an error reads the same from either engine.
 *  Covers what a node name can contain; not a general implementation. */
export function pyRepr(s: string): string {
  const quote = s.includes("'") && !s.includes('"') ? '"' : "'"
  const body = s
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t')
    .split(quote).join(`\\${quote}`)
  return `${quote}${body}${quote}`
}

/** Memoise a per-dataset index on the dataset object itself. Datasets are
 *  never mutated, so the object is a sound key, and a WeakMap lets one go. */
export function perDataset<T>(build: (ds: Dataset) => T): (ds: Dataset) => T {
  const cache = new WeakMap<Dataset, T>()
  return (ds) => {
    let value = cache.get(ds)
    if (value === undefined) {
      value = build(ds)
      cache.set(ds, value)
    }
    return value
  }
}

export function notHere(name: string): Error {
  return new Error(`Not in this dataset: ${pyRepr(name)}`)
}
