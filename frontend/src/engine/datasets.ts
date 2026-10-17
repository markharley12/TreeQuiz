/**
 * Every dataset under the repo's `datasets/`, found at build time.
 *
 * Adding a dataset is adding a directory: Vite's glob imports pick it up, so
 * nothing here names one. The manifests are small and imported outright, since
 * the front page lists every dataset; the trees and info are emitted as hashed
 * assets and fetched by URL on first use, because a page should not pay for
 * every tree to show one — and the popup text, the biggest file by far, is only
 * wanted once a popup opens.
 *
 * The files are read from `datasets/` in place, not copied into the frontend,
 * so there is one copy of each — which needs `server.fs.allow` in vite.config.
 */
import { makeDataset, type Dataset, type Manifest } from './tree'
import type { StoredInfo } from './info'

const manifests = import.meta.glob<Manifest>('../../../datasets/*/manifest.json', { eager: true, import: 'default' })
const treeUrls = import.meta.glob<string>('../../../datasets/*/tree.json', { eager: true, query: '?url', import: 'default' })
const infoUrls = import.meta.glob<string>('../../../datasets/*/info.json', { eager: true, query: '?url', import: 'default' })
const tierUrls = import.meta.glob<string>('../../../datasets/*/info-*.json', { eager: true, query: '?url', import: 'default' })

const idOf = (path: string) => path.split('/').slice(-2)[0]
const byId = <T>(files: Record<string, T>) => new Map(Object.entries(files).map(([p, v]) => [idOf(p), v]))
const trees = byId(treeUrls)
const infos = byId(infoUrls)

/** A sized tree's popup text in tiers: `info-<n>.json` holds what a cut to
 *  `n` adds to the stop before (see treequiz/size.py). Smallest first. */
export interface InfoTier {
  n: number
  url: string
}
const tiers = new Map<string, InfoTier[]>()
for (const [path, url] of Object.entries(tierUrls)) {
  const n = /\/info-(\d+)\.json$/.exec(path)?.[1]
  if (n === undefined) continue
  const id = idOf(path)
  tiers.set(id, [...(tiers.get(id) ?? []), { n: Number(n), url }].sort((a, b) => a.n - b.n))
}

export interface DatasetEntry {
  id: string
  manifest: Manifest
  hasInfo: boolean
}

/** Every playable dataset — one with a tree — in picker order. */
export const DATASETS: DatasetEntry[] = Object.entries(manifests)
  .map(([path, manifest]) => ({ id: idOf(path), manifest, hasInfo: infos.has(idOf(path)) || tiers.has(idOf(path)) }))
  .filter((d) => trees.has(d.id))
  .sort((a, b) => (a.manifest.order ?? 99) - (b.manifest.order ?? 99) || (a.id < b.id ? -1 : 1))

export const DEFAULT_DATASET = DATASETS[0]?.id ?? ''

export function entryFor(id: string): DatasetEntry | undefined {
  return DATASETS.find((d) => d.id === id)
}

/** Fetch once and share the result. A failure is not kept: on a phone the next
 *  attempt may have signal, and a cached rejection would end the session. */
function cachedFetch<T>(): (url: string) => Promise<T> {
  const pending = new Map<string, Promise<T>>()
  return (url) => {
    let p = pending.get(url)
    if (!p) {
      p = fetch(url)
        .then((res) => {
          if (!res.ok) throw new Error(`Could not load ${url}`)
          return res.json() as Promise<T>
        })
        .catch((e) => {
          pending.delete(url)
          throw e
        })
      pending.set(url, p)
    }
    return p
  }
}

const fetchTree = cachedFetch<Dataset['tree']>()
const fetchInfo = cachedFetch<Record<string, StoredInfo>>()
const built = new Map<string, Dataset>()

export async function loadDataset(id: string): Promise<Dataset> {
  const entry = entryFor(id)
  const url = trees.get(id)
  if (!entry || !url) throw new Error(`No dataset called ${id}`)
  const tree = await fetchTree(url)
  // One Dataset object per tree, so the engine's per-dataset indexes are built
  // once rather than per request.
  let ds = built.get(id)
  if (!ds || ds.tree !== tree) {
    ds = makeDataset(id, entry.manifest, tree)
    built.set(id, ds)
  }
  return ds
}

/** The dataset if `loadDataset` has already built it, without waiting. */
export function loadedDataset(id: string): Dataset | undefined {
  return built.get(id)
}

/** The tiers a tree cut to `upTo` needs: each up to the first that holds the
 *  whole cut. All of them for the whole tree, `upTo` left out. */
export function tiersUpTo<T extends { n: number }>(all: T[], upTo = Infinity): T[] {
  const last = all.findIndex((t) => t.n >= upTo)
  return last === -1 ? all : all.slice(0, last + 1)
}

const merged = new Map<string, Promise<Record<string, StoredInfo>>>()

/** Popup text for a tree, or for a sized tree cut to `upTo`: one `info.json`,
 *  or the tiers that size needs, fetched once each and read as one. */
export async function loadInfo(id: string, upTo?: number): Promise<Record<string, StoredInfo>> {
  const url = infos.get(id)
  if (url) return fetchInfo(url)
  const wanted = tiersUpTo(tiers.get(id) ?? [], upTo)
  if (wanted.length === 0) return {}
  const key = wanted.map((t) => t.url).join('\n')
  let all = merged.get(key)
  if (!all) {
    // No prototype, so a node named __proto__ is a key like any other.
    all = Promise.all(wanted.map((t) => fetchInfo(t.url)))
      .then((parts) => Object.assign(Object.create(null) as Record<string, StoredInfo>, ...parts))
    all.catch(() => merged.delete(key))
    merged.set(key, all)
  }
  return all
}

/** A localStorage key per dataset, so each keeps its own round. */
export function storageKey(key: string, dataset?: string): string {
  return dataset ? `treequiz:${key}:${dataset}` : `treequiz:${key}`
}
