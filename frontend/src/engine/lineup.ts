/**
 * Line-up. Port of `treequiz/lineup.py`, which explains why a puzzle always
 * has exactly one right order, what an ancestor must have to be a level, and
 * how difficulty is set; none of that is repeated here.
 *
 * Every draw is `seed.draw`, so a set is the same in both engines down to the
 * order its four names are shown in. As in odd one out, the order is drawn
 * with the *last* attempt's key, as Python's loop leaves it.
 */
import { bodyOf, draw, makeSeed, utcToday } from './seed'
import { leavesOf, lineageOfLeaf, warmthOf } from './game'
import { childrenOf, labelOf, perDataset, type Dataset, type RawNode } from './tree'
import type { Group } from './odd'

export const SET_SIZE = 5
export const OPTIONS = 4
export const TIER_OF = [0, 0, 1, 1, 2] as const
export const MAX_ATTEMPTS = 50

/** Every order of four, lexicographic, as Python's `itertools.permutations`. */
const PERMUTATIONS: number[][] = (() => {
  const out: number[][] = []
  const grow = (prefix: number[]) => {
    if (prefix.length === OPTIONS) out.push(prefix)
    for (let k = 0; k < OPTIONS; k++) if (!prefix.includes(k)) grow([...prefix, k])
  }
  grow([])
  return out
})()

export interface LineUp {
  target: string
  /** The four, in the order shown. */
  choices: string[]
  /** The four, nearest the target first: the answer. */
  order: string[]
  /** Where each of `order` meets the target, nearest first. */
  meets: Group[]
  tier: number
}

interface Shape {
  /** Each node's leaves as a run of the tree's leaves, [start, end). */
  span: Map<string, [number, number]>
  /** The leaves with at least OPTIONS levels, in tree order. */
  eligible: RawNode[]
}

const size = (span: Shape['span'], node: RawNode) => {
  const [start, end] = span.get(node.name)!
  return end - start
}

/** Where in `lineage` something else can meet the leaf at its end. */
export function levels(lineage: RawNode[], span: Shape['span']): number[] {
  const out: number[] = []
  for (let d = 0; d < lineage.length - 1; d++) if (size(span, lineage[d]) > size(span, lineage[d + 1])) out.push(d)
  return out
}

export const shape = perDataset((ds): Shape => {
  const span = new Map<string, [number, number]>()
  let count = 0
  const walk = (node: RawNode) => {
    const start = count
    const kids = childrenOf(node)
    if (kids.length === 0) count += 1
    kids.forEach(walk)
    span.set(node.name, [start, count])
  }
  walk(ds.tree)
  const eligible = leavesOf(ds).filter((leaf) => levels(lineageOfLeaf(ds, labelOf(leaf))!, span).length >= OPTIONS)
  return { span, eligible }
})

/** How many of a target's `m` levels, the deepest, a tier draws from. */
export function window(m: number, tier: number): number {
  return Math.max(OPTIONS, [m, Math.floor((2 * m + 2) / 3), Math.floor((m + 2) / 3)][tier])
}

function group(node: RawNode, warmth: number): Group {
  return { name: node.name, label: labelOf(node), rank: node.rank ?? '', warmth }
}

/** The `i`th puzzle of the set `body` names, avoiding the leaves in `used`. */
export function puzzle(ds: Dataset, body: string, i: number, used: Set<string>): LineUp {
  const { span, eligible } = shape(ds)
  if (eligible.length === 0) throw new Error(`No leaf of this tree has ${OPTIONS} levels to meet others at.`)
  const leaves = leavesOf(ds)
  const tier = TIER_OF[i % SET_SIZE]
  let key = ''
  let target = eligible[0]
  let lineage: RawNode[] = []
  let chosen: number[] = []
  let options: RawNode[] = []
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    key = `treequiz-lineup:${body}:${i}:${attempt}`
    target = eligible[draw(`${key}:target`, eligible.length)]
    lineage = lineageOfLeaf(ds, labelOf(target))!
    const found = levels(lineage, span)
    const w = window(found.length, tier)
    const deepest = found.slice(found.length - w)
    chosen = []
    for (let k = 0; k < OPTIONS; k++) {
      const lo = Math.floor((k * w) / OPTIONS)
      const hi = Math.floor(((k + 1) * w) / OPTIONS)
      chosen.push(deepest[lo + draw(`${key}:level${k}`, hi - lo)])
    }
    options = chosen.map((d, k) => {
      const [a0, a1] = span.get(lineage[d].name)!
      const [p0, p1] = span.get(lineage[d + 1].name)!
      const r = draw(`${key}:leaf${k}`, a1 - a0 - (p1 - p0))
      return r < p0 - a0 ? leaves[a0 + r] : leaves[p1 + r - (p0 - a0)]
    })
    if (![target, ...options].some((x) => used.has(x.name))) break
  }
  const nearest = [...options].reverse()
  const order = PERMUTATIONS[draw(`${key}:order`, PERMUTATIONS.length)]
  const warmth = warmthOf(ds)
  return {
    target: labelOf(target),
    choices: order.map((k) => labelOf(nearest[k])),
    order: nearest.map(labelOf),
    meets: [...chosen].reverse().map((d) => group(lineage[d], warmth.get(lineage[d].name)!)),
    tier,
  }
}

/** The five puzzles a seed names. Throws for a seed from another tree, or a
 *  tree with no line-up in it. */
export function makeSet(ds: Dataset, seed: string): LineUp[] {
  const body = bodyOf(seed, leavesOf(ds))
  const byLabel = new Map(leavesOf(ds).map((l) => [labelOf(l), l.name]))
  const used = new Set<string>()
  const out: LineUp[] = []
  for (let i = 0; i < SET_SIZE; i++) {
    const p = puzzle(ds, body, i, used)
    for (const label of [p.target, ...p.choices]) used.add(byLabel.get(label)!)
    out.push(p)
  }
  return out
}

/** A new set's seed: random, or the day's. */
export function pickSeed(ds: Dataset, opts: { daily?: boolean; today?: string } = {}): string {
  return makeSeed(leavesOf(ds), opts.daily ? { day: opts.today ?? utcToday() } : {})
}

/** How many of the four are in their right place, nearest first. */
export function score(p: LineUp, ranking: string[]): number {
  return ranking.filter((label, k) => label === p.order[k]).length
}
