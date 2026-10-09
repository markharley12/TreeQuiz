/**
 * Why a suggestion is on the list, when its name does not say. Typing
 * "fiddle" offers the xylophone, whose name holds no fiddle: it is there for
 * its alias "straw fiddle", and without that beside it the row reads as a
 * mistake. Display only — `suggest` decides what is offered, in both
 * languages; this only explains it, so it has no Python twin.
 */
import { leavesOf, matchTier } from './engine/game'
import { labelOf, type Dataset } from './engine/tree'

/** For each label in `labels` matched by an alias and not by itself, the best
 *  matching alias, ranked the way `suggest` ranks them. */
export function matchedAliases(ds: Dataset, query: string, labels: string[]): Map<string, string> {
  const needle = query.toLowerCase()
  const wanted = new Set(labels)
  const out = new Map<string, string>()
  for (const leaf of leavesOf(ds)) {
    const label = labelOf(leaf)
    if (!wanted.has(label) || matchTier(label, needle) !== null) continue
    let best: { alias: string, tier: number } | null = null
    for (const alias of leaf.aliases ?? []) {
      const tier = matchTier(alias, needle)
      if (tier !== null && (best === null || tier < best.tier)) best = { alias, tier }
    }
    if (best) out.set(label, best.alias)
  }
  return out
}
