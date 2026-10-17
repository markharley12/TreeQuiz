/**
 * The answer to a line-up, drawn as a ladder: the target's lineage from the
 * top down, a rung at each place one of the four meets it, that one hanging
 * off its rung, and the target at the foot. Reading down is reading nearer.
 *
 * Built from odd one out's boxes, so a rung carries the labels it skips and
 * a chess position reads as its moves. Display only, so no Python twin.
 */
import { lineageOfLeaf } from './engine/game'
import type { LineUp } from './engine/lineup'
import type { ChainStyle, Dataset } from './engine/tree'
import { box, type Box } from './oddReveal'

export interface Rung {
  /** Where the target and `option` meet. */
  meet: Box
  option: Box
  /** The option's place in the answer: 0 is nearest. */
  place: number
}

export interface Ladder {
  /** Farthest first: the order they are drawn in, top down. */
  rungs: Rung[]
  target: Box
}

export function ladder(ds: Dataset, p: LineUp): Ladder {
  const style: ChainStyle = ds.manifest
  const line = lineageOfLeaf(ds, p.target)!
  const depth = p.meets.map((m) => line.findIndex((n) => n.name === m.name))
  const rungs: Rung[] = []
  // The root is everyone's, so the top rung does not list it as skipped —
  // unless the top rung is the root.
  let from = Math.min(1, depth[depth.length - 1])
  for (let place = p.order.length - 1; place >= 0; place--) {
    const d = depth[place]
    const theirs = lineageOfLeaf(ds, p.order[place])!
    rungs.push({ meet: box(ds, line, from, d, style), option: box(ds, theirs, d + 1, theirs.length - 1, style), place })
    from = d + 1
  }
  return { rungs, target: box(ds, line, from, line.length - 1, style) }
}

/** "1st", "2nd", "3rd", "4th". */
export function ordinal(place: number): string {
  return `${place + 1}${['st', 'nd', 'rd'][place] ?? 'th'}`
}
