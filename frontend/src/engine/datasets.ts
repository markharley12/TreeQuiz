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

const idOf = (path: string) => path.split('/').slice(-2)[0]
const byId = <T>(files: Record<string, T>) => new Map(Object.entries(files).map(([p, v]) => [idOf(p), v]))
const trees = byId(treeUrls)
const infos = byId(infoUrls)

export interface DatasetEntry {
  id: string
  manifest: Manifest
  hasInfo: boolean
}

/** Every playable dataset — one with a tree — in picker order. */
export const DATASETS: DatasetEntry[] = Object.entries(manifests)
  .map(([path, manifest]) => ({ id: idOf(path), manifest, hasInfo: infos.has(idOf(path)) }))
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

export async function loadInfo(id: string): Promise<Record<string, StoredInfo>> {
  const url = infos.get(id)
  return url ? fetchInfo(url) : {}
}

/** A localStorage key per dataset, so each keeps its own round. */
export function storageKey(key: string, dataset?: string): string {
  return dataset ? `treequiz:${key}:${dataset}` : `treequiz:${key}`
}
