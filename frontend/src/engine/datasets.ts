/**
 * Every dataset under the repo's `datasets/`, found at build time.
 *
 * Adding a dataset is adding a directory: the build's catalogue (see
 * catalogue.ts) picks it up, so nothing here names one. The manifests are in
 * the catalogue, since the front page lists every tree, downloaded or not;
 * the trees and their popup text are files, which come through `readJson` —
 * the one door to a tree's files, which downloads.ts keeps on the device.
 * The popup text, the biggest file by far, is only read once a popup opens.
 */
import { makeDataset, type Dataset, type Manifest } from './tree'
import type { StoredInfo } from './info'
import { BAKED, filesOf, hasFile, manifestOf, onForget, readJson } from './downloads'

/** A sized tree's popup text in tiers: `info-<n>.json` holds what a cut to
 *  `n` adds to the stop before (see treequiz/size.py). Smallest first. Read
 *  from the tree's files, so a downloaded copy answers for its own version. */
export interface InfoTier {
  n: number
  name: string
}
function tiersOf(id: string): InfoTier[] {
  return filesOf(id)
    .flatMap((name) => {
      const n = /^info-(\d+)\.json$/.exec(name)?.[1]
      return n === undefined ? [] : [{ n: Number(n), name }]
    })
    .sort((a, b) => a.n - b.n)
}

export interface DatasetEntry {
  id: string
  manifest: Manifest
  /** Its leaf count, if the build had the tree. */
  leaves?: number
}

/** Every dataset there is — on the device or not — in picker order. A remote
 *  tree whose files this build lacks is listed only if it names a release,
 *  since then the website has it. */
export const DATASETS: DatasetEntry[] = [...BAKED.values()]
  .filter((d) => d.files || d.manifest.release)
  .map(({ id, manifest, leaves }) => ({ id, manifest, leaves }))
  .sort((a, b) => (a.manifest.order ?? 99) - (b.manifest.order ?? 99) || (a.id < b.id ? -1 : 1))

export const DEFAULT_DATASET = DATASETS[0]?.id ?? ''

export function entryFor(id: string): DatasetEntry | undefined {
  return DATASETS.find((d) => d.id === id)
}

/** Read once and share the result. A failure is not kept: on a phone the next
 *  attempt may have signal, and a cached rejection would end the session. */
const pending = new Map<string, Promise<unknown>>()
function read<T>(id: string, name: string): Promise<T> {
  const key = `${id}/${name}`
  let p = pending.get(key)
  if (!p) {
    p = readJson<T>(id, name).catch((e) => {
      pending.delete(key)
      throw e
    })
    pending.set(key, p)
  }
  return p as Promise<T>
}

const built = new Map<string, Dataset>()

// A copy replaced by an update, or deleted: read it afresh next time.
onForget((id) => {
  for (const key of [...pending.keys()]) if (key.startsWith(`${id}/`)) pending.delete(key)
  built.delete(id)
})

export async function loadDataset(id: string): Promise<Dataset> {
  if (!entryFor(id)) throw new Error(`No dataset called ${id}`)
  const tree = await read<Dataset['tree']>(id, 'tree.json')
  // One Dataset object per tree, so the engine's per-dataset indexes are built
  // once rather than per request.
  let ds = built.get(id)
  if (!ds || ds.tree !== tree) {
    ds = makeDataset(id, manifestOf(id)!, tree)
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
onForget((id) => {
  for (const key of [...merged.keys()]) if (key.startsWith(`${id}/`)) merged.delete(key)
})

/** Popup text for a tree, or for a sized tree cut to `upTo`: one `info.json`,
 *  or the tiers that size needs, read once each and merged as one. */
export async function loadInfo(id: string, upTo?: number): Promise<Record<string, StoredInfo>> {
  await loadDataset(id)
  if (hasFile(id, 'info.json')) return read(id, 'info.json')
  const wanted = tiersUpTo(tiersOf(id), upTo)
  if (wanted.length === 0) return {}
  const key = `${id}/` + wanted.map((t) => t.n).join(',')
  let all = merged.get(key)
  if (!all) {
    // No prototype, so a node named __proto__ is a key like any other.
    all = Promise.all(wanted.map((t) => read<Record<string, StoredInfo>>(id, t.name)))
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

/** Forget everything kept for one tree: its round, its view, its sets, its
 *  dailies and tallies — any `treequiz:<key>:<id>` key, and per-size keys
 *  after it (`…:<id>:2000`, `…:<id>@2000`). Settings are the whole app's and
 *  stay. Offered when a tree is deleted. */
export function forgetProgress(id: string) {
  const escaped = id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const mine = new RegExp(`^treequiz:[^:]+:${escaped}($|[:@])`)
  const keys: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && mine.test(key)) keys.push(key)
  }
  for (const key of keys) localStorage.removeItem(key)
}
