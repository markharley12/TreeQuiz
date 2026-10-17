/**
 * One tree at many sizes. Port of `treequiz/size.py`, which explains why a cut
 * is the sitelink threshold restated as a count, and why pass-throughs stay.
 */
import { childrenOf, leaves, type Manifest, type RawNode } from './tree'

export interface Sizes {
  min: number
  /** The size the daily is always played at. */
  default: number
  /** Where the slider snaps, below the whole tree. */
  stops: number[]
}

/** A tree's sizes, or null for a tree played whole. Python's validator has
 *  already refused a manifest whose sizes make no sense. */
export function sizesOf(manifest: Pick<Manifest, 'sizes'>): Sizes | null {
  const spec = manifest.sizes
  if (!spec) return null
  const stops = spec.stops?.length ? [...spec.stops] : [...new Set([spec.min, spec.default])].sort((a, b) => a - b)
  return { min: spec.min, default: spec.default, stops }
}

const fameOf = (leaf: RawNode) => leaf.fame || 0

/** Python's string order, which is by code point. JavaScript's `<` compares
 *  UTF-16 units, which disagrees where a character past U+FFFF (a surrogate
 *  pair) meets one in U+E000–U+FFFF; comparing code points at the first unit
 *  that differs agrees with Python everywhere. */
export function compareCodePoints(a: string, b: string): number {
  const n = Math.min(a.length, b.length)
  for (let i = 0; i < n; i++) {
    if (a.charCodeAt(i) !== b.charCodeAt(i)) return a.codePointAt(i)! - b.codePointAt(i)!
  }
  return a.length - b.length
}

/** Every leaf, best known first: fame descending, then name ascending. */
export function ranked(tree: RawNode): RawNode[] {
  return leaves(tree).sort((a, b) => fameOf(b) - fameOf(a) || compareCodePoints(a.name, b.name))
}

function keep(node: RawNode, kept: Set<string>): RawNode | null {
  const kids = childrenOf(node)
  if (kids.length === 0) return kept.has(node.name) ? node : null
  const out: RawNode[] = []
  for (const c of kids) {
    const k = keep(c, kept)
    if (k !== null) out.push(k)
  }
  if (out.length === 0) return null
  // An untouched subtree is the same object, so a cut shares what it keeps.
  if (out.length === kids.length && out.every((k, i) => k === kids[i])) return node
  return { ...node, children: out }
}

/** The tree with only its `n` best-known leaves, and the nodes above them.
 *  `n` at or past the leaf count is the whole tree, the same object. */
export function cut(tree: RawNode, n: number): RawNode {
  if (n < 1) throw new Error(`A tree cut to ${n} leaves has none; the smallest cut is 1.`)
  const order = ranked(tree)
  if (n >= order.length) return tree
  return keep(tree, new Set(order.slice(0, n).map((x) => x.name)))!
}
