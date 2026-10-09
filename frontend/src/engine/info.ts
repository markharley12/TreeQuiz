/**
 * A node's popup text. `info.json` holds only what the tree does not: the
 * label and rank are read from the tree and merged in on the way out, because a
 * second copy is free to disagree with the tree it describes.
 */
import { labelOf, perDataset, type Dataset, type RawNode } from './tree'

/** One entry of a dataset's `info.json`. Every field is optional. */
export interface StoredInfo {
  description?: string
  image_url?: string
  /** Where the text came from, and what to call the link. */
  url?: string
  url_title?: string
  /** What the node contains that the tree does not show — for a maths section,
   *  its MSC topics. */
  items?: string[]
  /** A line under the title, for what identifies the node beyond its label —
   *  a chess opening's moves. Not the source's text, so no licence follows it. */
  subtitle?: string
}

export interface Info extends StoredInfo {
  name: string
  label: string
  rank: string
}

const nodesOf = perDataset((ds) => {
  const out = new Map<string, RawNode>()
  const walk = (n: RawNode) => {
    out.set(n.name, n)
    for (const c of n.children ?? []) walk(c)
  }
  walk(ds.tree)
  return out
})

/** Null for a name the tree does not hold. A node with no stored text still
 *  answers, with its label and rank, so the popup can say what it is. */
export function infoFor(ds: Dataset, stored: Record<string, StoredInfo>, name: string): Info | null {
  const node = nodesOf(ds).get(name)
  if (!node) return null
  // Own properties only: `stored.constructor` is not a node.
  const entry = Object.prototype.hasOwnProperty.call(stored, name) ? stored[name] : {}
  return { ...entry, name, label: labelOf(node), rank: node.rank ?? '' }
}
