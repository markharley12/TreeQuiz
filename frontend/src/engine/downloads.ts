/**
 * Which trees live on this device: fetching, keeping, updating and deleting
 * them.
 *
 * Downloads are kept in a Cache Storage cache of their own, `treequiz-data`,
 * keyed by each file's URL — which carries the file's content hash, so a key
 * never means two things. The service worker's cache belongs to one build and
 * is deleted by the next deploy; this one belongs to the player, and nothing
 * but `remove` (or the browser evicting the site) deletes from it.
 *
 * Beside the files, each tree has a **copy**: a record of the version on the
 * device, its manifest and every file's URL, kept in the same cache so the two
 * are evicted together. The copy is what plays. A newer version on the server
 * does not replace it until it is downloaded whole, so a round in progress
 * keeps the tree its seed was dealt on:
 *
 * - **Small trees** (under ASK_BYTES) download themselves the first time
 *   they are opened, tree first so play starts at once and the popup text
 *   after it, and update themselves in the background the next time they are
 *   opened — the old copy plays meanwhile.
 * - **Big trees** ask first (`TreeState.offer.ask`, which the app shows as a
 *   download screen), and an update waits for the player to take it.
 *
 * Where Cache Storage is missing or refuses (an insecure origin, some private
 * windows, jsdom), the same code runs over a Map, and downloads last as long
 * as the page — which is what the app did before there were downloads.
 *
 * The same code serves the Android app (phase 5), from https://localhost:
 * there every tree is bundled into the app and read from it (vite.config.ts),
 * and `VITE_DATA_BASE` names the website, whose catalogue and files it would
 * fetch cross-origin (GitHub Pages answers `Access-Control-Allow-Origin: *`)
 * for a tree the app did not bundle — none today.
 */
import baked from 'virtual:treequiz-catalogue'
import { ASK_BYTES, downloadSet, sizeOf, type Catalogue, type CatalogueTree } from './catalogue'
import type { Manifest } from './tree'

export const DATA_CACHE = 'treequiz-data'

/** The page's own folder, which this build's files are relative to. */
const pageBase = () => new URL('.', document.baseURI).href
/** Where the live catalogue is: the website. The page's own folder there, and
 *  the website named by VITE_DATA_BASE in the app. */
const dataBase = () => import.meta.env.VITE_DATA_BASE || pageBase()

interface Located {
  version: string
  manifest: Manifest
  files: Record<string, { href: string; bytes: number; gzip: number }>
}

/** A tree on the device. Written once its first file is in; `have` lists the
 *  files held, which may be fewer than `files` — the rest are fetched when
 *  first asked for. */
interface Copy extends Located {
  id: string
  have: string[]
}

export const BAKED: ReadonlyMap<string, CatalogueTree> = new Map(baked.trees.map((t) => [t.id, t]))

/** Every tree is part of the app (the Android build bundles them all), so
 *  there is nothing to download or delete, and no Manage trees. */
export const ALL_BUNDLED = BAKED.size > 0 && [...BAKED.values()].every((t) => t.bundled)

function locate(entry: CatalogueTree, base: string): Located | null {
  if (!entry.files || !entry.version) return null
  const files: Located['files'] = {}
  for (const [name, f] of Object.entries(entry.files)) files[name] = { href: new URL(f.url, base).href, bytes: f.bytes, gzip: f.gzip }
  return { version: entry.version, manifest: entry.manifest, files }
}

// --- The store: Cache Storage, or a Map standing in for it -------------------

interface Store {
  match(key: string): Promise<Response | undefined>
  put(key: string, res: Response): Promise<void>
  delete(key: string): Promise<boolean>
  keys(): Promise<string[]>
}

function memoryStore(): Store {
  const held = new Map<string, ArrayBuffer>()
  return {
    match: async (key) => {
      const body = held.get(key)
      return body && new Response(body, { headers: { 'Content-Type': 'application/json' } })
    },
    put: async (key, res) => { held.set(key, await res.arrayBuffer()) },
    delete: async (key) => held.delete(key),
    keys: async () => [...held.keys()],
  }
}

async function openStore(): Promise<{ store: Store; lasting: boolean }> {
  try {
    if (typeof caches !== 'undefined') {
      const cache = await caches.open(DATA_CACHE)
      return {
        lasting: true,
        store: {
          match: (key) => cache.match(key),
          put: (key, res) => cache.put(key, res),
          delete: (key) => cache.delete(key),
          keys: async () => (await cache.keys()).map((r) => r.url),
        },
      }
    }
  } catch {
    // Firefox's private windows refuse Cache Storage with a SecurityError.
  }
  return { store: memoryStore(), lasting: false }
}

const copyKey = (id: string) => `${pageBase()}treequiz-copy/${encodeURIComponent(id)}`

// --- State ---------------------------------------------------------------------

let store: Store = memoryStore()
/** Whether downloads outlive the page. */
let lasting = false
const copies = new Map<string, Copy>()
/** The live catalogue, once fetched: newer than this build's, if a deploy has
 *  happened since, and the only one in the app that knows the big trees. */
let live: Map<string, Located> | null = null

interface Job {
  done: number
  total: number
  abort: AbortController
  promise: Promise<void>
}
const jobs = new Map<string, Job>()
const errors = new Map<string, string>()
/** Files being fetched, by URL, so two askers share one download. */
const inflight = new Map<string, Promise<void>>()
/** Trees whose background update has been tried this page. */
const autoUpdated = new Set<string>()

const channel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel(DATA_CACHE) : null

/**
 * A copy this build cannot play as an older version of its tree, which is
 * deleted rather than kept: a tree no longer in the catalogue, or one that has
 * become a sized tree or stopped being one. The second is a different game
 * under the same name — its rounds are kept under other keys (sizes.ts), so
 * the old copy keeps no saved round alive — as when the Wikidata animals took
 * the name `animals` from TaxoQuiz's curated 530 (Oct 2026). Kept, the 530
 * would have played on as `animals` behind an "Update" button, and the 10MB
 * of the old `animals-full` sat on the device with nothing to show it.
 */
function gone(copy: Copy): boolean {
  const entry = BAKED.get(copy.id)
  return !entry || !sameKind(entry.manifest, copy.manifest)
}

/** Whether two manifests are one tree's versions rather than two games under
 *  one name: both sized, or neither. A live catalogue's entry that is not is
 *  ignored too — the app built for the Wikidata animals, meeting a website
 *  still serving the 530 as `animals`, would otherwise have downloaded them
 *  and played them under the sized manifest. */
function sameKind(a: Manifest, b: Manifest): boolean {
  return Boolean(a.sizes) === Boolean(b.sizes)
}

async function readCopies() {
  copies.clear()
  const prefix = copyKey('')
  const stale: Copy[] = []
  for (const key of await store.keys()) {
    if (!key.startsWith(prefix)) continue
    try {
      const copy = await (await store.match(key))?.json() as Copy | undefined
      if (!copy?.id) continue
      if (gone(copy)) stale.push(copy)
      else copies.set(copy.id, copy)
    } catch {
      // A record that will not parse is no copy; its files are re-fetched.
    }
  }
  for (const copy of stale) {
    await store.delete(copyKey(copy.id))
    for (const f of Object.values(copy.files)) await store.delete(f.href)
  }
}

let loaded = false
const ready: Promise<void> = (async () => {
  ({ store, lasting } = await openStore())
  await readCopies()
  loaded = true
  changed()
})()

/** Resolves once the device's copies are known. */
export const whenReady = () => ready

// Another tab downloaded or deleted something.
channel?.addEventListener('message', () => {
  void ready.then(readCopies).then(changed)
})

async function saveCopy(copy: Copy) {
  copies.set(copy.id, copy)
  await store.put(copyKey(copy.id), new Response(JSON.stringify(copy), { headers: { 'Content-Type': 'application/json' } }))
}

// --- What the app reads ----------------------------------------------------------

/** The newest version of a tree known: the live catalogue's, else this build's.
 *  A bundled tree is the app's own, and the app's update is its update. */
function newest(id: string): Located | null {
  const entry = BAKED.get(id)
  if (!entry) return null
  if (entry.bundled) return locate(entry, pageBase())
  return live?.get(id) ?? locate(entry, pageBase())
}

const needsAsk = (offer: Located) => sizeOf(offer, downloadSet(offer)).bytes > ASK_BYTES

/** Thrown when a big tree is opened before the player has agreed to download it. */
export class NeedsDownload extends Error {
  constructor(public id: string) {
    super(`${id} has to be downloaded first`)
  }
}

/** Has the file? Answers from the copy on the device, else the newest version. */
export function hasFile(id: string, name: string): boolean {
  return filesOf(id).includes(name)
}

/** The names of a tree's files (`tree.json`, `info.json`, `info-<n>.json`):
 *  the copy's on the device, else the newest version's. */
export function filesOf(id: string): string[] {
  return Object.keys((copies.get(id) ?? newest(id))?.files ?? {}).sort()
}

/** The manifest of the tree that plays: the copy's, which may be older than
 *  this build's. */
export function manifestOf(id: string): Manifest | undefined {
  return copies.get(id)?.manifest ?? BAKED.get(id)?.manifest
}

/**
 * One of a tree's files, by its name in `datasets/<id>/` — `tree.json`,
 * `info.json`, `info-<n>.json`. This is the one door every tree file comes
 * through: from the app itself if bundled, else from the copy on the device,
 * downloading the tree first if it is small and not here yet.
 */
export async function readJson<T>(id: string, name: string): Promise<T> {
  await ready
  const entry = BAKED.get(id)
  if (!entry) throw new Error(`No dataset called ${id}`)
  if (entry.bundled) {
    const href = locate(entry, pageBase())?.files[name]?.href
    if (!href) throw new Error(`${id} has no ${name}`)
    const res = await fetch(href)
    if (!res.ok) throw new Error(`Could not load ${href}`)
    return res.json()
  }
  let copy = copies.get(id)
  if (!copy) {
    const offer = newest(id)
    if (!offer) throw new Error(`${entry.manifest.title} is not available here`)
    if (needsAsk(offer)) throw new NeedsDownload(id)
    await download(id, name)
    copy = copies.get(id)
    if (!copy) throw new Error(errors.get(id) ?? `Could not download ${entry.manifest.title}`)
  } else if (!autoUpdated.has(id)) {
    // A small tree takes a newer version in the background; this page goes on
    // with the copy it has, and the next one opens the new.
    autoUpdated.add(id)
    const offer = newest(id)
    if (offer && offer.version !== copy.version && !needsAsk(offer) && !jobs.has(id)) download(id).catch(() => {})
  }
  return (await held(copy, name)).json()
}

/** A file of the copy, fetched into the store if it has not been yet. */
async function held(copy: Copy, name: string): Promise<Response> {
  const file = copy.files[name]
  if (!file) throw new Error(`${copy.id} has no ${name}`)
  const hit = await store.match(file.href)
  if (hit) return hit
  await fetchInto(file.href, null, () => {})
  // The copy may have been replaced while that ran; mark the one now held.
  const now = copies.get(copy.id)
  if (now && now.files[name]?.href === file.href && !now.have.includes(name)) {
    await saveCopy({ ...now, have: [...now.have, name] })
    changed()
  }
  const res = await store.match(file.href)
  if (!res) throw new Error(`Could not keep ${file.href}`)
  return res
}

class HttpError extends Error {
  constructor(public status: number, href: string) {
    super(status === 404 ? `${href} is no longer on the server` : `Could not load ${href} (${status})`)
  }
}

/** Fetch a file into the store, counting the bytes as they arrive. */
function fetchInto(href: string, signal: AbortSignal | null, onBytes: (n: number) => void): Promise<void> {
  let p = inflight.get(href)
  if (p) return p
  p = (async () => {
    // Not into the HTTP cache as well: a 45MB file kept twice.
    const res = await fetch(href, { signal, cache: 'no-store' })
    if (!res.ok) throw new HttpError(res.status, href)
    let body: Response = res
    if (res.body) {
      // One branch is stored, the other counted.
      const [keep, count] = res.body.tee()
      body = new Response(keep)
      void (async () => {
        const reader = count.getReader()
        try {
          for (;;) {
            const { done, value } = await reader.read()
            if (done) break
            onBytes(value.length)
          }
        } catch {
          // The stored branch reports the failure.
        }
      })()
    }
    await store.put(href, new Response(body.body, { headers: { 'Content-Type': 'application/json' } }))
  })().finally(() => inflight.delete(href))
  inflight.set(href, p)
  return p
}

/**
 * Download a tree, or its newest version over the copy on the device.
 *
 * With `first`, that file comes first and the copy is written as soon as it
 * is in, so a small tree plays while its popup text follows. An update writes
 * the new copy only once every file is in, so the old one plays until then
 * and stays whole if the download fails. Shares a download already running.
 */
export function download(id: string, first?: string): Promise<void> {
  const running = jobs.get(id)
  if (running) return first ? untilHeld(id, first, running) : running.promise
  const offer = newest(id)
  if (!offer) return Promise.reject(new Error(`No files for ${id}`))
  const before = copies.get(id)
  // Whatever the device holds at the same URL is the same bytes, so an update
  // that changed only the manifest, or one file, fetches only what changed.
  const keep = before ? before.have.filter((n) => before.files[n]?.href === offer.files[n]?.href) : []
  const names = downloadSet(offer)
  if (first && !names.includes(first) && offer.files[first]) names.push(first)
  const order = [...names.filter((n) => n === (first ?? 'tree.json')), ...names.filter((n) => n !== (first ?? 'tree.json'))]
  const todo = order.filter((n) => !keep.includes(n))

  const job: Job = { done: 0, total: sizeOf(offer, todo).bytes, abort: new AbortController(), promise: Promise.resolve() }
  jobs.set(id, job)
  errors.delete(id)
  changed()
  let tick = 0
  const progress = (n: number) => {
    job.done += n
    const now = Date.now()
    if (now - tick > 100) { tick = now; changed() }
  }

  job.promise = (async () => {
    const put: string[] = []
    const have = [...keep]
    try {
      for (const name of todo) {
        const href = offer.files[name].href
        try {
          await fetchInto(href, job.abort.signal, progress)
        } catch (e) {
          // A page older than the site asked for files a deploy has replaced:
          // look again at what the site has, and start over from that.
          if (e instanceof HttpError && e.status === 404 && !live) {
            await refresh()
            if (live && newest(id)?.version !== offer.version) {
              jobs.delete(id)
              return download(id)
            }
          }
          throw e
        }
        put.push(href)
        have.push(name)
        job.abort.signal.throwIfAborted()
        // A first download is playable once its first file is in; an update
        // replaces the copy only when whole.
        if (!before || before.version === offer.version) {
          await saveCopy({ id, ...offer, have: [...have] })
          changed()
        }
      }
      if (before && before.version !== offer.version) {
        await saveCopy({ id, ...offer, have })
        const now = new Set(Object.values(offer.files).map((f) => f.href))
        for (const f of Object.values(before.files)) if (!now.has(f.href)) await store.delete(f.href)
        forgetLoaded(id)
      }
      if (sizeOf(offer, have).bytes > ASK_BYTES) void keepDownloads()
      channel?.postMessage('changed')
    } catch (e) {
      // A cancelled first download leaves nothing behind. A failed one keeps
      // what plays already, and an update keeps the old copy whole.
      if (!before && job.abort.signal.aborted && copies.get(id)?.version === offer.version) {
        copies.delete(id)
        await store.delete(copyKey(id)).catch(() => false)
      }
      if (copies.get(id)?.version !== offer.version) {
        for (const href of put) await store.delete(href).catch(() => false)
      }
      if (!job.abort.signal.aborted) errors.set(id, e instanceof Error ? e.message : String(e))
      throw e
    } finally {
      if (jobs.get(id) === job) jobs.delete(id)
      changed()
    }
  })()
  return first ? untilHeld(id, first, job) : job.promise
}

/** Resolves once `name` is held — the moment a first download is playable. */
function untilHeld(id: string, name: string, job: Job): Promise<void> {
  return new Promise((resolve, reject) => {
    const check = () => {
      if (copies.get(id)?.have.includes(name)) { off(); resolve() }
    }
    const off = subscribe(check)
    job.promise.then(() => { off(); resolve() }, (e) => { off(); reject(e) })
    check()
  })
}

/** Stop a download. A first download keeps nothing; an update, the old copy. */
export function cancel(id: string) {
  jobs.get(id)?.abort.abort()
}

/** Delete a tree from the device. A bundled tree cannot be. */
export async function remove(id: string): Promise<void> {
  await ready
  const job = jobs.get(id)
  if (job) {
    job.abort.abort()
    await job.promise.catch(() => {})
  }
  const copy = copies.get(id)
  if (!copy) return
  copies.delete(id)
  await store.delete(copyKey(id))
  for (const f of Object.values(copy.files)) await store.delete(f.href)
  autoUpdated.delete(id)
  forgetLoaded(id)
  channel?.postMessage('changed')
  changed()
}

/** Ask the browser not to evict downloads under storage pressure: asked once
 *  something big is down. Chrome answers by its own measure of engagement,
 *  without a prompt; Firefox asks the player. */
async function keepDownloads() {
  try {
    if (!navigator.storage?.persist || await navigator.storage.persisted()) return
    await navigator.storage.persist()
  } catch {
    // Not offered: downloads are kept as long as the browser chooses.
  }
}

/** Fetch the live catalogue: how a page learns of newer trees, and the app of
 *  big ones. Asked once at start, and again when trees are managed. A failure
 *  (offline) leaves things as they were. */
let refreshing: Promise<void> | null = null
export function refresh(): Promise<void> {
  refreshing ??= (async () => {
    try {
      const url = new URL('datasets.json', dataBase()).href
      const res = await fetch(url, { cache: 'no-cache' })
      if (!res.ok) return
      const catalogue = await res.json() as Catalogue
      const next = new Map<string, Located>()
      for (const entry of catalogue.trees) {
        const baked = BAKED.get(entry.id)
        const located = baked && sameKind(baked.manifest, entry.manifest) ? locate(entry, url) : null
        if (located) next.set(entry.id, located)
      }
      live = next
      changed()
    } catch {
      // Offline, or no catalogue there: this build's own is what there is.
    } finally {
      refreshing = null
    }
  })()
  return refreshing
}

// --- Forgetting what is loaded in memory ---------------------------------------

const forgetters = new Set<(id: string) => void>()
/** Called when a tree's copy is replaced or deleted, so whatever was parsed
 *  from it is dropped. */
export function onForget(fn: (id: string) => void) {
  forgetters.add(fn)
}
function forgetLoaded(id: string) {
  for (const fn of forgetters) fn(id)
}

// --- For the screens ---------------------------------------------------------------

export interface TreeState {
  id: string
  manifest: Manifest
  /** Part of the app: on the device from install, never deleted. */
  bundled: boolean
  /** Big enough to ask before downloading (over ASK_BYTES). */
  big: boolean
  /** What the device holds of it. `missing` is what a download would still
   *  fetch of the files it fetches up front. A bundled tree's bytes are
   *  compressed, as the APK holds them; a download's are as stored. */
  copy: { version: string; bytes: number; missing: number } | null
  /** What downloading it, or updating it, costs: null when the device has the
   *  newest, or no version is to be had (a remote tree the build lacked,
   *  offline). `ask` when it is big enough to ask first. */
  offer: { bytes: number; gzip: number; ask: boolean } | null
  /** The offer is a newer version of the copy. */
  update: boolean
  progress: { done: number; total: number } | null
  error: string | null
}

function stateOf(id: string): TreeState {
  const entry = BAKED.get(id)!
  const copy = copies.get(id)
  const top = newest(id)
  const job = jobs.get(id)
  let held: TreeState['copy'] = null
  if (entry.bundled && top) {
    // All of it is in the app, not only what a download would fetch first,
    // and compressed: Android keeps an APK's assets deflated and never
    // unpacks them, so the gzip size is what the tree takes on the phone
    // (animals: 45.6MB as text, 9.7MB in the APK).
    held = { version: top.version, bytes: sizeOf(top, Object.keys(top.files)).gzip, missing: 0 }
  } else if (copy) {
    const want = downloadSet(copy).filter((n) => !copy.have.includes(n))
    held = { version: copy.version, bytes: sizeOf(copy, copy.have).bytes, missing: sizeOf(copy, want).bytes }
  }
  const newer = top && !entry.bundled && top.version !== copy?.version ? top : null
  const cost = newer && sizeOf(newer, downloadSet(newer).filter((n) => newer.files[n].href !== copy?.files[n]?.href))
  return {
    id,
    manifest: entry.manifest,
    bundled: Boolean(entry.bundled),
    big: Boolean((top ?? copy) && needsAsk((top ?? copy)!)),
    copy: held,
    offer: newer && cost ? { ...cost, ask: needsAsk(newer) } : null,
    update: Boolean(newer && copy),
    progress: job ? { done: Math.min(job.done, job.total), total: job.total } : null,
    error: errors.get(id) ?? null,
  }
}

export interface Downloads {
  /** False until the device's copies have been read: before then every tree
   *  would look missing, and a big one would flash its download screen. */
  ready: boolean
  /** Whether downloads outlive the page: false where Cache Storage is refused. */
  lasting: boolean
  trees: ReadonlyMap<string, TreeState>
}

const listeners = new Set<() => void>()
let snapshot: Downloads = { ready: false, lasting: false, trees: new Map() }

function changed() {
  snapshot = { ready: loaded, lasting, trees: new Map([...BAKED.keys()].map((id) => [id, stateOf(id)])) }
  for (const fn of [...listeners]) fn()
}

export function subscribe(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/** Every tree's state, replaced whole on any change (for useSyncExternalStore). */
export function downloads(): Downloads {
  return snapshot
}

changed()
