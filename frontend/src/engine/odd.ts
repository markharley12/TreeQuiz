/**
 * Odd one out. Port of `treequiz/odd.py`, which explains why a puzzle always
 * has exactly one answer, how difficulty is set, and why meeting nodes are
 * drawn by size; none of that is repeated here.
 *
 * Every draw is `seed.draw`, so a set is the same in both engines down to the
 * order its three names are shown in. The loop below keeps Python's habit of
 * using the *last* attempt's key for the order after the loop ends.
 */
import { bodyOf, draw, makeSeed, utcToday } from './seed'
import { leavesOf, lineageOfLeaf, warmthOf } from './game'
import { childrenOf, labelOf, perDataset, type Dataset, type RawNode } from './tree'

export const SET_SIZE = 10
export const TIER_OF = [0, 0, 0, 1, 1, 1, 1, 2, 2, 2] as const
export const MAX_ATTEMPTS = 50
const ORDERS = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]] as const

interface Meeting {
  node: RawNode
  warmth: number
  /** Each child's leaves, in tree order. */
  kids: RawNode[][]
  /** How many leaves below: what the node is drawn in proportion to. */
  size: number
}

export interface Group {
  name: string
  label: string
  rank: string
  warmth: number
}

export interface Puzzle {
  /** The three, in the order shown. */
  choices: string[]
  odd: string
  pair: [string, string]
  /** Where the pair meets. */
  group: Group
  /** Where all three meet. */
  shared: Group
  tier: number
}

/** The tree's meeting nodes by warmth, coolest first, in three tiers. */
export const tiers = perDataset((ds): Meeting[][] => {
  const warmth = warmthOf(ds)
  const points: Meeting[] = []
  const walk = (node: RawNode): RawNode[] => {
    const kids = childrenOf(node)
    if (kids.length === 0) return [node]
    const under = kids.map(walk)
    if (under.length >= 2 && under.some((u) => u.length >= 2)) {
      points.push({ node, warmth: warmth.get(node.name)!, kids: under, size: under.reduce((s, u) => s + u.length, 0) })
    }
    return under.flat()
  }
  walk(ds.tree)
  const preorder = new Map<string, number>()
  const order = (n: RawNode) => {
    preorder.set(n.name, preorder.size)
    childrenOf(n).forEach(order)
  }
  order(ds.tree)
  points.sort((a, b) => a.warmth - b.warmth || preorder.get(a.node.name)! - preorder.get(b.node.name)!)
  const n = points.length
  return [0, 1, 2].map((t) => points.slice(Math.floor((t * n) / 3), Math.floor(((t + 1) * n) / 3)))
})

function weighted(pool: Meeting[], r: number): Meeting {
  for (const m of pool) {
    if (r < m.size) return m
    r -= m.size
  }
  throw new Error('r is drawn below the pool\'s total size')
}

function group(node: RawNode, warmth: number): Group {
  return { name: node.name, label: labelOf(node), rank: node.rank ?? '', warmth }
}

function lca(a: RawNode[], b: RawNode[]): RawNode {
  let result = a[0]
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i].name !== b[i].name) break
    result = a[i]
  }
  return result
}

/** The `i`th puzzle of the set `body` names, avoiding the leaves in `used`. */
export function puzzle(ds: Dataset, body: string, i: number, used: Set<string>): Puzzle {
  const tiered = tiers(ds)
  const tier = TIER_OF[i % SET_SIZE]
  const pool = tiered[tier].length ? tiered[tier] : tiered.flat()
  if (pool.length === 0) throw new Error('No three of this tree\'s leaves have two closer than the third.')
  const total = pool.reduce((s, m) => s + m.size, 0)
  let key = ''
  let meet = pool[0]
  let a = pool[0].node
  let b = a
  let c = a
  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    key = `treequiz-odd:${body}:${i}:${attempt}`
    meet = weighted(pool, draw(`${key}:meet`, total))
    const pairable = meet.kids.flatMap((u, k) => (u.length >= 2 ? [k] : []))
    const k1 = pairable[draw(`${key}:pair`, pairable.length)]
    const others = meet.kids.flatMap((_, k) => (k !== k1 ? [k] : []))
    const k2 = others[draw(`${key}:odd`, others.length)]
    const under = meet.kids[k1]
    const ia = draw(`${key}:a`, under.length)
    let ib = draw(`${key}:b`, under.length - 1)
    if (ib >= ia) ib += 1
    a = under[ia]
    b = under[ib]
    c = meet.kids[k2][draw(`${key}:c`, meet.kids[k2].length)]
    if (!used.has(a.name) && !used.has(b.name) && !used.has(c.name)) break
  }
  const trio = [a, b, c]
  const order = ORDERS[draw(`${key}:order`, ORDERS.length)]
  const pair = lca(lineageOfLeaf(ds, labelOf(a))!, lineageOfLeaf(ds, labelOf(b))!)
  return {
    choices: order.map((k) => labelOf(trio[k])),
    odd: labelOf(c),
    pair: [labelOf(a), labelOf(b)],
    group: group(pair, warmthOf(ds).get(pair.name)!),
    shared: group(meet.node, meet.warmth),
    tier,
  }
}

/** The ten puzzles a seed names. Throws for a seed from another tree, or a
 *  tree with no puzzle in it. */
export function makeSet(ds: Dataset, seed: string): Puzzle[] {
  const body = bodyOf(seed, leavesOf(ds))
  const byLabel = new Map(leavesOf(ds).map((l) => [labelOf(l), l.name]))
  const used = new Set<string>()
  const out: Puzzle[] = []
  for (let i = 0; i < SET_SIZE; i++) {
    const p = puzzle(ds, body, i, used)
    for (const label of p.choices) used.add(byLabel.get(label)!)
    out.push(p)
  }
  return out
}

/** A new set's seed: random, or the day's. */
export function pickSeed(ds: Dataset, opts: { daily?: boolean; today?: string } = {}): string {
  return makeSeed(leavesOf(ds), opts.daily ? { day: opts.today ?? utcToday() } : {})
}
