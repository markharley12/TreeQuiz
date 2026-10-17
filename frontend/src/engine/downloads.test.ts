/**
 * Trees on the device: downloading, keeping, updating and deleting them.
 *
 * Each test builds its own catalogue and serves its own files, and Cache
 * Storage is a Map that outlives `vi.resetModules()` — so a "deploy" is a fresh
 * module over a new catalogue with the same cache underneath, which is the
 * thing the separate data cache exists to survive.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Catalogue, CatalogueTree } from './catalogue'

const MB = 1_000_000

/** A tree whose files are `{name: body}`, at sizes the catalogue claims. */
function entry(id: string, version: string, files: Record<string, { bytes?: number }>, extra: Partial<CatalogueTree> = {}): CatalogueTree {
  return {
    id, version, manifest: { title: id },
    files: Object.fromEntries(Object.entries(files).map(([name, f]) => [
      name, { url: `data/${id}/${name.replace('.json', '')}-${version}.json`, bytes: f.bytes ?? 100, gzip: Math.ceil((f.bytes ?? 100) / 5) },
    ])),
    ...extra,
  }
}

/** What the server has: by URL, and its catalogue. */
let served = new Map<string, string>()
let fetched: string[] = []
let liveCatalogue: Catalogue | null = null

function serve(catalogue: Catalogue, bodies: Record<string, Record<string, unknown>>) {
  for (const t of catalogue.trees) {
    for (const [name, f] of Object.entries(t.files ?? {})) {
      served.set(new URL(f.url, document.baseURI).href, JSON.stringify(bodies[t.id][name]))
    }
  }
}

/** Cache Storage as a Map of Maps, kept across module reloads. */
const storage = new Map<string, Map<string, ArrayBuffer>>()
const fakeCaches = {
  open: async (name: string) => {
    let held = storage.get(name)
    if (!held) storage.set(name, held = new Map())
    const h = held
    return {
      match: async (key: string) => {
        const body = h.get(key)
        return body && new Response(body.slice(0))
      },
      put: async (key: string, res: Response) => { h.set(key, await res.arrayBuffer()) },
      delete: async (key: string) => h.delete(key),
      keys: async () => [...h.keys()].map((url) => ({ url })),
    }
  },
}

async function load(catalogue: Catalogue) {
  vi.resetModules()
  vi.doMock('virtual:treequiz-catalogue', () => ({ default: catalogue }))
  const mod = await import('./downloads')
  await mod.whenReady()
  return mod
}

const tree = (id: string) => ({ name: id, children: [{ name: `${id} leaf` }] })

beforeEach(() => {
  served = new Map()
  fetched = []
  liveCatalogue = null
  storage.clear()
  vi.stubGlobal('caches', fakeCaches)
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    fetched.push(url)
    await Promise.resolve()
    init?.signal?.throwIfAborted()
    if (url.endsWith('/datasets.json')) {
      return liveCatalogue ? new Response(JSON.stringify(liveCatalogue)) : new Response(null, { status: 404 })
    }
    const body = served.get(url)
    return body === undefined ? new Response(null, { status: 404 }) : new Response(body)
  }))
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.doUnmock('virtual:treequiz-catalogue')
})

const small = entry('small', 'v1', { 'tree.json': {}, 'info.json': {} })
const big = entry('big', 'b1', { 'tree.json': { bytes: 6 * MB }, 'info.json': { bytes: 40 * MB } })
const bodies = {
  small: { 'tree.json': tree('small'), 'info.json': { 'small leaf': { description: 'v1 text' } } },
  big: { 'tree.json': tree('big'), 'info.json': { 'big leaf': { description: 'big text' } } },
}

describe('a small tree', () => {
  it('downloads itself the first time it is read, tree first, and keeps it', async () => {
    serve({ trees: [small] }, bodies)
    const d = await load({ trees: [small] })
    expect(d.downloads().trees.get('small')).toMatchObject({ copy: null, offer: { ask: false }, big: false })

    expect(await d.readJson('small', 'tree.json')).toEqual(tree('small'))
    expect(fetched[0]).toMatch(/small\/tree-v1\.json$/)
    await vi.waitFor(() => expect(d.downloads().trees.get('small')?.progress).toBeNull())
    expect(d.downloads().trees.get('small')?.copy).toEqual({ version: 'v1', bytes: 200, missing: 0 })

    // Kept: the next page reads it from the device, with the server gone.
    served.clear()
    const again = await load({ trees: [small] })
    expect(await again.readJson('small', 'info.json')).toEqual(bodies.small['info.json'])
  })

  it('takes a newer version in the background, playing the old one meanwhile', async () => {
    serve({ trees: [small] }, bodies)
    const d = await load({ trees: [small] })
    await d.readJson('small', 'tree.json')
    await vi.waitFor(() => expect(d.downloads().trees.get('small')?.progress).toBeNull())

    // A deploy: the build's catalogue names v2, at new URLs.
    const v2 = entry('small', 'v2', { 'tree.json': {}, 'info.json': {} })
    serve({ trees: [v2] }, { small: { ...bodies.small, 'info.json': { 'small leaf': { description: 'v2 text' } } } })
    const after = await load({ trees: [v2] })
    expect(after.downloads().trees.get('small')).toMatchObject({ copy: { version: 'v1' }, update: true })
    // This page plays v1 …
    expect(await after.readJson('small', 'info.json')).toEqual(bodies.small['info.json'])
    // … while v2 comes down, replacing it whole.
    await vi.waitFor(() => expect(after.downloads().trees.get('small')?.copy?.version).toBe('v2'))
    expect([...storage.get('treequiz-data')!.keys()].filter((k) => k.includes('-v1.'))).toEqual([])
  })
})

describe('a big tree', () => {
  it('will not download until asked, then says how far it has got', async () => {
    serve({ trees: [big] }, bodies)
    const d = await load({ trees: [big] })
    expect(d.downloads().trees.get('big')).toMatchObject({ copy: null, big: true, offer: { ask: true, bytes: 46 * MB } })
    await expect(d.readJson('big', 'tree.json')).rejects.toBeInstanceOf(d.NeedsDownload)
    expect(fetched).toEqual([])

    const done = d.download('big')
    expect(d.downloads().trees.get('big')?.progress).toMatchObject({ done: 0, total: 46 * MB })
    await done
    expect(d.downloads().trees.get('big')).toMatchObject({ copy: { version: 'b1', missing: 0 }, offer: null, progress: null })
    expect(await d.readJson('big', 'tree.json')).toEqual(tree('big'))
  })

  it('keeps the old copy playing until the player takes an update', async () => {
    serve({ trees: [big] }, bodies)
    const d = await load({ trees: [big] })
    await d.download('big')

    const b2 = entry('big', 'b2', { 'tree.json': { bytes: 6 * MB }, 'info.json': { bytes: 40 * MB } })
    serve({ trees: [b2] }, { big: { ...bodies.big, 'tree.json': tree('big2') } })
    const after = await load({ trees: [big] })
    liveCatalogue = { trees: [b2] }
    await after.refresh()
    // The website has b2; the device plays b1 and offers the update.
    expect(after.downloads().trees.get('big')).toMatchObject({ copy: { version: 'b1' }, update: true, offer: { ask: true } })
    expect(await after.readJson('big', 'tree.json')).toEqual(tree('big'))
    expect(fetched.filter((u) => u.includes('b2'))).toEqual([])

    const forgot: string[] = []
    after.onForget((id) => forgot.push(id))
    await after.download('big')
    expect(after.downloads().trees.get('big')).toMatchObject({ copy: { version: 'b2' }, update: false })
    expect(forgot).toEqual(['big'])
    expect(await after.readJson('big', 'tree.json')).toEqual(tree('big2'))
  })

  it('fetches only the files an update changed', async () => {
    serve({ trees: [big] }, bodies)
    const d = await load({ trees: [big] })
    await d.download('big')
    // A new manifest, the same files: the URLs carry the files' hashes, not the version's.
    const b2 = { ...big, version: 'b2', manifest: { title: 'big, retitled' } }
    const after = await load({ trees: [b2] })
    expect(after.downloads().trees.get('big')).toMatchObject({ update: true, offer: { bytes: 0 } })
    fetched = []
    await after.download('big')
    expect(fetched).toEqual([])
    expect(after.downloads().trees.get('big')).toMatchObject({ copy: { version: 'b2', missing: 0 }, update: false })
    expect(after.manifestOf('big')?.title).toBe('big, retitled')
  })

  it('keeps nothing of a cancelled download', async () => {
    serve({ trees: [big] }, bodies)
    const d = await load({ trees: [big] })
    const done = d.download('big')
    d.cancel('big')
    await expect(done).rejects.toThrow()
    expect(d.downloads().trees.get('big')).toMatchObject({ copy: null, progress: null, error: null })
    expect([...(storage.get('treequiz-data')?.keys() ?? [])]).toEqual([])
  })

  it('asks the browser to keep downloads once one is big', async () => {
    const persist = vi.fn(async () => true)
    vi.stubGlobal('navigator', { ...navigator, storage: { persisted: async () => false, persist } })
    serve({ trees: [big, small] }, bodies)
    const d = await load({ trees: [big, small] })
    await d.readJson('small', 'tree.json')
    await vi.waitFor(() => expect(d.downloads().trees.get('small')?.progress).toBeNull())
    expect(persist).not.toHaveBeenCalled()
    await d.download('big')
    await vi.waitFor(() => expect(persist).toHaveBeenCalledTimes(1))
  })
})

describe('deleting', () => {
  it('removes the files and the copy, so the tree is downloadable again', async () => {
    serve({ trees: [small, big] }, bodies)
    const d = await load({ trees: [small, big] })
    await d.download('big')
    await d.readJson('small', 'tree.json')
    await vi.waitFor(() => expect(d.downloads().trees.get('small')?.progress).toBeNull())

    await d.remove('big')
    expect(d.downloads().trees.get('big')).toMatchObject({ copy: null, offer: { ask: true } })
    const keys = [...storage.get('treequiz-data')!.keys()]
    expect(keys.some((k) => k.includes('big'))).toBe(false)
    expect(keys.some((k) => k.includes('small'))).toBe(true)
  })
})

describe('a copy the catalogue no longer plays', () => {
  it('is deleted when its tree is gone, or has become a sized tree', async () => {
    serve({ trees: [small, big] }, bodies)
    let d = await load({ trees: [small, big] })
    await d.download('big')
    await d.readJson('small', 'tree.json')
    await vi.waitFor(() => expect(d.downloads().trees.get('small')?.progress).toBeNull())

    // A deploy: big is gone, and small is now sized — a different game.
    const sized = entry('small', 'v2', { 'tree.json': {}, 'info.json': {} }, { manifest: { title: 'small', sizes: { min: 1, default: 1 } } })
    d = await load({ trees: [sized] })
    expect(d.downloads().trees.get('small')?.copy).toBeNull()
    expect([...storage.get('treequiz-data')!.keys()]).toEqual([])
  })
})

describe('without Cache Storage', () => {
  it('still plays, holding downloads for the page only', async () => {
    vi.stubGlobal('caches', undefined)
    serve({ trees: [small] }, bodies)
    const d = await load({ trees: [small] })
    expect(d.downloads().lasting).toBe(false)
    expect(await d.readJson('small', 'tree.json')).toEqual(tree('small'))
  })
})

describe('the app (bundled trees, and a remote catalogue)', () => {
  it('reads a bundled tree from the app itself and learns big ones from the website', async () => {
    const bundled = { ...small, bundled: true }
    serve({ trees: [bundled] }, bodies)
    const d = await load({ trees: [bundled, { ...big, files: null, version: null }] })
    expect(d.downloads().trees.get('small')).toMatchObject({ bundled: true, copy: { bytes: 200 }, offer: null })
    expect(d.downloads().trees.get('big')).toMatchObject({ copy: null, offer: null })
    expect(await d.readJson('small', 'tree.json')).toEqual(tree('small'))
    expect(storage.get('treequiz-data')?.size ?? 0).toBe(0)

    serve({ trees: [big] }, bodies)
    liveCatalogue = { trees: [big] }
    await d.refresh()
    expect(d.downloads().trees.get('big')).toMatchObject({ offer: { ask: true } })
  })
})

describe('forgetting a tree', () => {
  it("clears its round, sets and dailies, per size too, and no other tree's", async () => {
    vi.resetModules()
    const { forgetProgress } = await import('./datasets')
    localStorage.clear()
    for (const key of ['session:animals', 'oddtally:animals', 'daily:animals', 'session:animals:2000', 'session:animals@2000',
                       'session:animals-full', 'session:maths']) localStorage.setItem(`treequiz:${key}`, '1')
    localStorage.setItem('treequiz:settings', '{}')
    forgetProgress('animals')
    expect(Object.keys(localStorage).sort()).toEqual(['treequiz:session:animals-full', 'treequiz:session:maths', 'treequiz:settings'])
  })
})
