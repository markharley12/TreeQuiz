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
import { BAKED, hasFile, manifestOf, onForget, readJson } from './downloads'

export interface DatasetEntry {
  id: string
  manifest: Manifest
}

/** Every dataset there is — on the device or not — in picker order. A remote
 *  tree whose files this build lacks is listed only if it names a release,
 *  since then the website has it. */
export const DATASETS: DatasetEntry[] = [...BAKED.values()]
  .filter((d) => d.files || d.manifest.release)
  .map(({ id, manifest }) => ({ id, manifest }))
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

export async function loadInfo(id: string): Promise<Record<string, StoredInfo>> {
  await loadDataset(id)
  return hasFile(id, 'info.json') ? read(id, 'info.json') : {}
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
