/**
 * Free browsing of a tree. Port of `treequiz/explore.py`, which explains the
 * node budget, `truncated`, and why a lineage comes back in one piece.
 */
import { warmthByName } from './ladder'
import { childrenOf, labelOf, notHere, perDataset, type Dataset, type RawNode } from './tree'

export interface ExploreNode {
  name: string
  label: string
  rank: string
  depth: number
  /** How specific this node is, 0..1 — what it is coloured by. */
  warmth: number
  child_count: number
  leaf_count: number
  /** Total descendants including this node — what a full expand would render. */
  node_count: number
  /** Has children this slice does not hold. Opening it needs another fetch. */
  truncated: boolean
  children: ExploreNode[]
}

export interface ExploreHit {
  name: string
  label: string
  rank: string
  depth: number
  leaf_count: number
  is_leaf: boolean
}

export interface ExploreStats {
  root: string
  nodes: number
  leaves: number
  max_depth: number
}

export interface Lineage {
  path: string[]
  tree: ExploreNode
}

interface ExploreIndex {
  tree: RawNode
  byName: Map<string, RawNode>
  parent: Map<string, string>
  depth: Map<string, number>
  leafCount: Map<string, number>
  nodeCount: Map<string, number>
  warmth: Map<string, number>
}

const exploreIndex = perDataset((ds): ExploreIndex => {
  const byName = new Map<string, RawNode>()
  const parent = new Map<string, string>()
  const depth = new Map<string, number>()
  const leafCount = new Map<string, number>()
  const nodeCount = new Map<string, number>()

  const walk = (node: RawNode, parentName: string | null, d: number): [number, number] => {
    const name = node.name
    byName.set(name, node)
    depth.set(name, d)
    if (parentName !== null) parent.set(name, parentName)
    const kids = childrenOf(node)
    if (kids.length === 0) {
      leafCount.set(name, 1)
      nodeCount.set(name, 1)
      return [1, 1]
    }
    let lv = 0, nodes = 0
    for (const child of kids) {
      const [a, b] = walk(child, name, d + 1)
      lv += a
      nodes += b
    }
    leafCount.set(name, lv)
    nodeCount.set(name, nodes + 1)
    return [lv, nodes + 1]
  }
  walk(ds.tree, null, 0)
  return { tree: ds.tree, byName, parent, depth, leafCount, nodeCount, warmth: warmthByName(ds.tree, ds.ladder) }
})

/** Names to include, grown a whole level at a time until a limit bites. `null` is no limit. */
function select(node: RawNode, depth: number | null, budget: number | null): Set<string> {
  const included = new Set([node.name])
  let frontier = [node]
  let level = 0
  while (frontier.length > 0 && (depth === null || level < depth)) {
    const next = frontier.flatMap(childrenOf)
    if (next.length === 0) break
    if (budget !== null && included.size + next.length > budget) break
    for (const n of next) included.add(n.name)
    frontier = next
    level += 1
  }
  return included
}

/** `included === null` serialises the node alone, as a stub. */
function nodeDict(node: RawNode, included: Set<string> | null, idx: ExploreIndex): ExploreNode {
  const name = node.name
  const kids = childrenOf(node)
  const kept = included === null ? [] : kids.filter((c) => included.has(c.name))
  return {
    name,
    label: labelOf(node),
    rank: node.rank ?? '',
    depth: idx.depth.get(name)!,
    warmth: idx.warmth.get(name)!,
    child_count: kids.length,
    leaf_count: idx.leafCount.get(name)!,
    node_count: idx.nodeCount.get(name)!,
    truncated: kept.length < kids.length,
    children: kept.map((c) => nodeDict(c, included, idx)),
  }
}

export function subtree(
  ds: Dataset,
  root: string | null = null,
  depth: number | null = null,
  budget: number | null = 200,
): ExploreNode {
  const idx = exploreIndex(ds)
  const node = root === null ? idx.tree : idx.byName.get(root)
  if (node === undefined) throw notHere(root!)
  return nodeDict(node, select(node, depth, budget), idx)
}

export function pathTo(ds: Dataset, name: string): string[] {
  const idx = exploreIndex(ds)
  if (!idx.byName.has(name)) throw notHere(name)
  const chain = [name]
  while (idx.parent.has(chain[chain.length - 1])) chain.push(idx.parent.get(chain[chain.length - 1])!)
  return chain.reverse()
}

export const LINEAGE_TARGET_BUDGET = 60

export function lineage(ds: Dataset, name: string): Lineage {
  const idx = exploreIndex(ds)
  const chain = pathTo(ds, name)
  const build = (node: RawNode, i: number): ExploreNode => {
    if (i + 1 >= chain.length) return nodeDict(node, select(node, null, LINEAGE_TARGET_BUDGET), idx)
    const next = chain[i + 1]
    const out = nodeDict(node, null, idx)
    out.children = childrenOf(node).map((c) => (c.name === next ? build(c, i + 1) : nodeDict(c, null, idx)))
    out.truncated = false
    return out
  }
  return { path: chain, tree: build(idx.tree, 0) }
}

/** Nodes whose label, name or an alias contains the query: prefix matches
 *  first, then bigger groups, then by name. */
export function search(ds: Dataset, query: string, limit = 25): ExploreHit[] {
  const idx = exploreIndex(ds)
  const needle = query.trim().toLowerCase()
  if (!needle) return []
  const hits: { prefix: number; size: number; node: RawNode }[] = []
  for (const [name, node] of idx.byName) {
    const hays = [labelOf(node).toLowerCase(), name.toLowerCase(), ...(node.aliases ?? []).map((a) => a.toLowerCase())]
    const matched = hays.filter((h) => h.includes(needle))
    if (matched.length === 0) continue
    const prefix = matched.some((h) => h.startsWith(needle)) ? 0 : 1
    hits.push({ prefix, size: idx.leafCount.get(name)!, node })
  }
  hits.sort((a, b) =>
    a.prefix - b.prefix || b.size - a.size || (a.node.name < b.node.name ? -1 : a.node.name > b.node.name ? 1 : 0))
  return hits.slice(0, limit).map(({ node }) => ({
    name: node.name,
    label: labelOf(node),
    rank: node.rank ?? '',
    depth: idx.depth.get(node.name)!,
    leaf_count: idx.leafCount.get(node.name)!,
    is_leaf: childrenOf(node).length === 0,
  }))
}

export function stats(ds: Dataset): ExploreStats {
  const idx = exploreIndex(ds)
  let maxDepth = 0
  for (const d of idx.depth.values()) if (d > maxDepth) maxDepth = d
  const root = idx.tree.name
  return { root, nodes: idx.nodeCount.get(root)!, leaves: idx.leafCount.get(root)!, max_depth: maxDepth }
}
