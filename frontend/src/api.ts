/**
 * Everything the app asks about a dataset, answered on the device.
 *
 * TaxoQuiz decided here whether a question went to its server or to the
 * engine; TreeQuiz has no server, so every answer is the engine's. The async
 * signatures stay: a dataset's tree is fetched on first use, and the components
 * should not care whether it already has been.
 */
import { DATASETS, entryFor, loadDataset, loadInfo } from './engine/datasets'
import { getGameState, pick, suggest } from './engine/game'
import { lineage, search, stats, subtree } from './engine/explore'
import { infoFor, type Info } from './engine/info'
import { tagOf, fingerprint } from './engine/seed'
import { leavesOf } from './engine/game'
import { matchedAliases } from './aliasHint'

export type { TreeNode } from './engine/game'
export type { ExploreNode, ExploreHit, ExploreStats, Lineage } from './engine/explore'
export type { Info } from './engine/info'
import type { TreeNode } from './engine/game'
import type { ExploreNode, ExploreHit, ExploreStats, Lineage } from './engine/explore'

export interface NewRound {
  secret: string
  seed: string
  daily: boolean
}

/** Start a round. Pass a seed to replay someone else's exactly. Rejects with a
 *  message for the player if the seed is malformed or for another dataset. */
export async function startRound(dataset: string, opts: { daily?: boolean; seed?: string } = {}): Promise<NewRound> {
  const round = pick(await loadDataset(dataset), { daily: opts.daily, seed: opts.seed })
  return { ...round, daily: Boolean(opts.daily) && !opts.seed }
}

export async function fetchSuggestions(dataset: string, q: string, limit = 50, exclude: string[] = []): Promise<string[]> {
  return suggest(await loadDataset(dataset), q, limit, exclude)
}

/** Why each of `labels` was suggested for `q`, where its name does not say. */
export async function fetchMatchedAliases(dataset: string, q: string, labels: string[]): Promise<Map<string, string>> {
  return matchedAliases(await loadDataset(dataset), q, labels)
}

/** Null for a round with no guesses and no hints, which the app never asks for. */
export async function fetchGameState(dataset: string, secret: string, guesses: string[], hints = 0): Promise<TreeNode | null> {
  return getGameState(await loadDataset(dataset), secret, guesses, hints)
}

export async function fetchInfo(dataset: string, name: string): Promise<Info | null> {
  const [ds, stored] = await Promise.all([loadDataset(dataset), loadInfo(dataset)])
  return infoFor(ds, stored, name)
}

/** `budget: -1` fetches every descendant. */
export async function fetchExplore(dataset: string, root?: string, budget = 200): Promise<ExploreNode> {
  return subtree(await loadDataset(dataset), root ?? null, null, budget === -1 ? null : budget)
}

/** Jump to a node: the whole spine from the root, with siblings, in one call. */
export async function fetchLineage(dataset: string, name: string): Promise<Lineage> {
  return lineage(await loadDataset(dataset), name)
}

export async function searchExplore(dataset: string, q: string, limit = 25): Promise<ExploreHit[]> {
  return search(await loadDataset(dataset), q, limit)
}

export async function fetchStats(dataset: string): Promise<ExploreStats> {
  return stats(await loadDataset(dataset))
}

/** The dataset a seed was made on, if it is one of ours. A seed's first four
 *  characters fingerprint its dataset's leaves, so a seed alone says where it
 *  belongs — which is what lets a pasted seed switch dataset rather than only
 *  being refused. Loads every tree to find out, so it is asked only once a seed
 *  has been rejected by the current one. */
export async function datasetForSeed(seed: string): Promise<string | null> {
  const tag = tagOf(seed)
  if (tag === null) return null
  for (const { id } of DATASETS) {
    try {
      if (fingerprint(leavesOf(await loadDataset(id))) === tag) return id
    } catch {
      // A tree that will not load cannot be the one; keep looking.
    }
  }
  return null
}

export { DATASETS, entryFor }
