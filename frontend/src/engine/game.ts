/**
 * The guessing game. Port of `treequiz/game.py`; the reasoning behind the `???`
 * marker, its warmth and hints lives there and is not repeated here.
 */
import { warmthByName } from './ladder'
import { makeSeed, normalise, resolve, utcToday } from './seed'
import { childrenOf, isLeaf, labelOf, leaves, notHere, perDataset, type Dataset, type RawNode } from './tree'

/** A node of the display tree a round draws. */
export interface TreeNode {
  /** The tree's own name — the key for info. Null on the ??? node, which has
   *  nothing to look up. */
  name: string | null
  label: string
  /** Blank on the ??? node, whose rank would say how far below the answer sits. */
  rank?: string
  /** On the ??? node only: whether a hint has anything left to reveal. */
  can_hint?: boolean
  node_type: 'ancestor' | 'guess' | 'secret'
  depth: number
  on_secret_path: boolean
  /** How specific this node is, 0..1 — what it is coloured by. */
  warmth: number
  /** Guesses only: the depth and the warmth of the LCA with the secret. */
  lca_depth?: number
  lca_warmth?: number
  children: TreeNode[]
}

interface GameIndex {
  leaves: RawNode[]
  /** Keyed by label: that is what a player guesses. */
  byLabel: Map<string, RawNode>
  lineageOf: Map<string, RawNode[]>
  depthOf: Map<string, number>
  warmth: Map<string, number>
}

const gameIndex = perDataset((ds): GameIndex => {
  const byLabel = new Map<string, RawNode>()
  const lineageOf = new Map<string, RawNode[]>()
  const depthOf = new Map<string, number>()
  const walk = (node: RawNode, path: RawNode[], depth: number) => {
    depthOf.set(node.name, depth)
    if (isLeaf(node)) {
      byLabel.set(labelOf(node), node)
      lineageOf.set(labelOf(node), [...path, node])
    }
    for (const child of childrenOf(node)) walk(child, [...path, node], depth + 1)
  }
  walk(ds.tree, [], 0)
  return { leaves: leaves(ds.tree), byLabel, lineageOf, depthOf, warmth: warmthByName(ds.tree, ds.ladder) }
})

export function leavesOf(ds: Dataset): RawNode[] {
  return gameIndex(ds).leaves
}

/** The deepest node both lineages share. */
function lca(a: RawNode[], b: RawNode[]): RawNode {
  let result = a[0]
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    if (a[i].name !== b[i].name) break
    result = a[i]
  }
  return result
}

/** The annotated display tree for a round, or null with no guesses and no
 *  hints, as in Python. Names are leaf labels. */
export function getGameState(ds: Dataset, secret: string, guesses: string[], hints = 0): TreeNode | null {
  const idx = gameIndex(ds)
  for (const name of [secret, ...guesses]) {
    if (!idx.byLabel.has(name)) throw notHere(name)
  }

  const secretLineage = idx.lineageOf.get(secret)!
  const secretNames = new Set(secretLineage.map((n) => n.name))
  const guessLineages = guesses.map((g) => idx.lineageOf.get(g)!)
  const guessNames = new Set(guesses.map((g) => idx.byLabel.get(g)!.name))

  const lcaDepth = new Map<string, number>()
  const lcaWarmth = new Map<string, number>()
  guesses.forEach((g, i) => {
    const shared = lca(secretLineage, guessLineages[i])
    const name = idx.byLabel.get(g)!.name
    lcaDepth.set(name, idx.depthOf.get(shared.name)!)
    lcaWarmth.set(name, idx.warmth.get(shared.name)!)
  })

  const show = new Set<string>()
  for (const lin of guessLineages) for (const node of lin) show.add(node.name)

  let marker: string | null = null
  let canHint = false
  if (guessLineages.length > 0 || hints > 0) {
    let deepestDepth = 0
    let deepestIdx = 0
    for (const lin of guessLineages) {
      const shared = lca(secretLineage, lin)
      const d = idx.depthOf.get(shared.name)!
      if (d > deepestDepth) {
        deepestDepth = d
        deepestIdx = secretLineage.findIndex((n) => n.name === shared.name)
      }
    }
    const last = secretLineage.length - 1
    if (deepestIdx < last) {
      const known = Math.min(deepestIdx + Math.max(hints, 0), last - 1)
      for (const node of secretLineage.slice(0, known + 1)) show.add(node.name)
      marker = secretLineage[known + 1].name
      show.add(marker)
      canHint = known + 1 < last
    }
  }

  const prune = (node: RawNode, parentWarmth: number): TreeNode | null => {
    const name = node.name
    if (!show.has(name)) return null
    const kind = name === marker ? 'secret' : guessNames.has(name) ? 'guess' : 'ancestor'
    const own = kind === 'secret' ? parentWarmth : idx.warmth.get(name)!
    const children: TreeNode[] = []
    for (const child of childrenOf(node)) {
      const pruned = prune(child, own)
      if (pruned !== null) children.push(pruned)
    }
    const out: TreeNode = {
      name: kind === 'secret' ? null : name,
      label: kind === 'secret' ? '???' : labelOf(node),
      rank: kind === 'secret' ? '' : (node.rank ?? ''),
      node_type: kind,
      depth: idx.depthOf.get(name)!,
      warmth: own,
      on_secret_path: secretNames.has(name),
      children,
    }
    if (kind === 'guess') {
      out.lca_depth = lcaDepth.get(name) ?? 0
      out.lca_warmth = lcaWarmth.get(name) ?? 0.0
    }
    if (kind === 'secret') out.can_hint = canHint
    return out
  }
  return prune(ds.tree, 0.0)
}

/** The secret leaf's label, and the seed that names it. Throws for a malformed
 *  seed or one from another dataset. */
export function pick(
  ds: Dataset,
  opts: { seed?: string; daily?: boolean; today?: string } = {},
): { secret: string; seed: string } {
  const lv = leavesOf(ds)
  if (opts.seed) return { secret: labelOf(resolve(opts.seed, lv)), seed: normalise(opts.seed) }
  const full = makeSeed(lv, opts.daily ? { day: opts.today ?? utcToday() } : {})
  return { secret: labelOf(resolve(full, lv)), seed: full }
}

const isWordChar = (c: string | undefined) => c !== undefined && /[a-z0-9]/.test(c)
const TIERS = 5

/** 0 exact, 1 the name's last word, 2 a whole word elsewhere, 3 the start of a
 *  word, 4 anywhere, null for no match. `needle` is lower-cased by the caller.
 *  Port of `game.match_tier`, which says why. */
export function matchTier(name: string, needle: string): number | null {
  const low = name.toLowerCase()
  if (low === needle) return 0
  // Also what stops the loop below: indexOf('', n) never returns -1.
  if (!needle) return 4
  const coreEnd = low.replace(/[ ]*(\([^)]*\))?[ ]*(#[0-9]+)?$/, '').length
  let best: number | null = null
  let i = low.indexOf(needle)
  while (i !== -1) {
    const j = i + needle.length
    const before = i === 0 || !isWordChar(low[i - 1])
    const after = j === low.length || !isWordChar(low[j])
    const tier = before && after ? (j === coreEnd ? 1 : 2) : before ? 3 : 4
    if (best === null || tier < best) best = tier
    i = low.indexOf(needle, i + 1)
  }
  return best
}

/** Up to `limit` leaf labels matching `query`, best first: label matches by
 *  tier, then alias-only matches by tier, tree order within each. */
export function suggest(ds: Dataset, query: string, limit = 50, exclude: string[] = []): string[] {
  const needle = query.toLowerCase()
  const skip = new Set(exclude)
  const tiers: string[][] = Array.from({ length: TIERS * 2 }, () => [])
  for (const leaf of leavesOf(ds)) {
    const label = labelOf(leaf)
    if (skip.has(label)) continue
    let tier = matchTier(label, needle)
    if (tier === null) {
      let best: number | null = null
      for (const alias of leaf.aliases ?? []) {
        const t = matchTier(alias, needle)
        if (t !== null && (best === null || t < best)) best = t
      }
      if (best !== null) tier = TIERS + best
    }
    if (tier !== null) tiers[tier].push(label)
  }
  return tiers.flat().slice(0, limit)
}
