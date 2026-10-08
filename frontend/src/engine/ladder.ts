/**
 * Warmth, 0..1: what both trees are coloured by and what a guess scores. Port
 * of `treequiz/ladder.py`, which holds the reasoning — the anchors, why a rank
 * is a claim checked against the tree, interpolation, the tie toward the longer
 * path. It is not repeated here, so that there is one place to read it.
 *
 * The port must be exact: `conformance.test.ts` compares every number to
 * Python's with `===`, not a tolerance.
 */
import { childrenOf, type Ladder, type RawNode } from './tree'

export function levelOf(rank: string | null | undefined, ladder: Ladder): number | null {
  if (!rank) return null
  return ladder.levels.get(rank.trim().toLowerCase()) ?? null
}

const toWarmth = (level: number, ladder: Ladder) => Math.min(Math.max(level / ladder.top, 0.0), 1.0)

/** A value every node was given, where `null` is a real answer. */
const at = <T>(map: Map<RawNode, T>, node: RawNode) => map.get(node) as T

/** Each node's level, or null where it has none or the tree contradicts it. */
export function believedLevels(tree: RawNode, ladder: Ladder): Map<RawNode, number | null> {
  const raw = new Map<RawNode, number | null>()
  const parMax = new Map<RawNode, number | null>()
  const minDesc = new Map<RawNode, number | null>()

  const down = (node: RawNode, best: number | null, isRoot: boolean) => {
    const own = childrenOf(node).length === 0 ? ladder.top : isRoot ? 0.0 : levelOf(node.rank, ladder)
    raw.set(node, own)
    parMax.set(node, best)
    const deeper = own === null ? best : best === null ? own : Math.max(best, own)
    for (const child of childrenOf(node)) down(child, deeper, false)
  }
  down(tree, null, true)

  const up = (node: RawNode): number | null => {
    let best: number | null = null
    for (const child of childrenOf(node)) {
      for (const cand of [up(child), at(raw, child)]) {
        if (cand !== null && (best === null || cand < best)) best = cand
      }
    }
    minDesc.set(node, best)
    return best
  }
  up(tree)

  const believed = new Map<RawNode, number | null>()
  const judge = (node: RawNode, isRoot: boolean) => {
    const own = at(raw, node)
    let keep = own
    if (own !== null && !isRoot && childrenOf(node).length > 0) {
      const above = at(parMax, node), below = at(minDesc, node)
      if ((above !== null && own <= above) || (below !== null && own >= below)) keep = null
    }
    believed.set(node, keep)
    for (const child of childrenOf(node)) judge(child, false)
  }
  judge(tree, true)
  return believed
}

/** Every node name mapped to its warmth, 0..1. */
export function warmthByName(tree: RawNode, ladder: Ladder): Map<string, number> {
  const believed = believedLevels(tree, ladder)
  const out = new Map<string, number>()

  const below = new Map<RawNode, [number, number] | null>()
  const broadestBelow = (node: RawNode): [number, number] | null => {
    let best: [number, number] | null = null
    for (const child of childrenOf(node)) {
      const deeper = broadestBelow(child)
      const own = at(believed, child)
      const cand: [number, number] | null =
        own !== null ? [own, 1] : deeper === null ? null : [deeper[0], deeper[1] + 1]
      if (cand !== null && (best === null || cand[0] < best[0] || (cand[0] === best[0] && cand[1] > best[1]))) {
        best = cand
      }
    }
    below.set(node, best)
    return best
  }
  broadestBelow(tree)

  const walkDown = (node: RawNode, anc: number, steps: number, floor: number) => {
    const own = at(believed, node)
    let value: number
    if (own !== null) {
      value = toWarmth(own, ladder)
      anc = own
      steps = 0
    } else {
      steps += 1
      const found = at(below, node)
      if (found === null) {
        value = toWarmth(anc, ladder)
      } else {
        const [desc, downSteps] = found
        value = toWarmth(anc + (desc - anc) * (steps / (steps + downSteps)), ladder)
        if (value <= floor) value = floor + (toWarmth(desc, ladder) - floor) / (downSteps + 1)
      }
      value = Math.max(value, floor)
    }
    out.set(node.name, value)
    for (const child of childrenOf(node)) walkDown(child, anc, steps, value)
  }
  walkDown(tree, 0.0, 0, 0.0)
  return out
}
