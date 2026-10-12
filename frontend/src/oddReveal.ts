/**
 * The answer to an odd-one-out puzzle, drawn as the tree of its three leaves:
 * where all three meet, then a fork — the pair's group on one side, splitting
 * again into the pair; the odd one alone on the other.
 *
 * Each box is one node, carrying the labels of the nodes it skips (`above`):
 * the three lineages have only five nodes worth drawing between them, and the
 * rest is context. Display only, over the engine's own lineages, so there is
 * no Python twin.
 */
import { lineageOfLeaf, warmthOf } from './engine/game'
import type { Puzzle } from './engine/odd'
import { labelOf, type ChainStyle, type Dataset, type RawNode } from './engine/tree'
import { joinSteps } from './gameLayout'

/** The most skipped labels a box shows, nearest first kept: eleven ranks above
 *  Boreoeutheria were four lines of small print over a one-word box. Moves are
 *  kept whole, since a line of moves is what a chess position is. */
export const ABOVE_MAX = 3

export interface Box {
  /** The node's name, for its popup. */
  name: string
  /** What the box says: its label, or where labels are steps of a path, the
   *  steps since the box above. */
  text: string
  /** The skipped nodes between the box above and this one, as one line;
   *  empty if none. */
  above: string
  /** How a sentence names it: its label, or its whole path from the root. */
  full: string
  rank: string
  warmth: number
}

export interface Reveal {
  shared: Box
  group: Box
  /** The pair, then the odd one. */
  pair: [Box, Box]
  odd: Box
}

function box(ds: Dataset, lineage: RawNode[], from: number, at: number, style: ChainStyle): Box {
  const node = lineage[at]
  const skipped = lineage.slice(from, at).map(labelOf)
  const stepwise = style.chain_order === 'root_first'
  const leaf = at === lineage.length - 1
  // Steps of a path read as one path: a position is named by every move since
  // the box above; a leaf keeps its own name, with those moves under it.
  const text = stepwise && !leaf ? joinSteps([...skipped, labelOf(node)], style) : labelOf(node)
  const near = skipped.length > ABOVE_MAX ? ['…', ...skipped.slice(-ABOVE_MAX)] : skipped
  const above = stepwise ? (leaf ? joinSteps(skipped, style) : '') : near.join(' › ')
  const full = stepwise && !leaf && at > 0 ? joinSteps(lineage.slice(1, at + 1).map(labelOf), style) : labelOf(node)
  return { name: node.name, text, above, full, rank: node.rank ?? '', warmth: warmthOf(ds).get(node.name)! }
}

export function reveal(ds: Dataset, p: Puzzle): Reveal {
  const style: ChainStyle = ds.manifest
  const [a, b] = p.pair.map((l) => lineageOfLeaf(ds, l)!)
  const c = lineageOfLeaf(ds, p.odd)!
  const s = c.findIndex((n) => n.name === p.shared.name)
  const g = a.findIndex((n) => n.name === p.group.name)
  // The root is everyone's, so it is left out of what the top box skips —
  // unless the root is where the three meet.
  return {
    shared: box(ds, c, Math.min(1, s), s, style),
    group: box(ds, a, s + 1, g, style),
    pair: [box(ds, a, g + 1, a.length - 1, style), box(ds, b, g + 1, b.length - 1, style)],
    odd: box(ds, c, s + 1, c.length - 1, style),
  }
}

/** One sentence saying why: "Paris and Lyon share France; Berlin meets them
 *  only at Western Europe." A chess position is named by its whole line. */
export function because(p: Puzzle, r: Reveal, display: (label: string) => string): string {
  const [a, b] = p.pair.map(display)
  return `${a} and ${b} share ${r.group.full}; ${display(p.odd)} meets them only at ${r.shared.full}.`
}
