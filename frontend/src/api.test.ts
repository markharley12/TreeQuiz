/**
 * The registry and the API in front of the engine, over the real datasets.
 *
 * The engine's answers are checked against Python in engine/conformance.test.ts.
 * This is about what sits in front of it: that every directory under datasets/
 * is found, that a tree is fetched once and a failed fetch is not kept, and that
 * a seed finds its own tree.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'

const files = import.meta.glob<string>('../../datasets/*/{tree,info}.json', { eager: true, query: '?raw', import: 'default' })

/** Serve each dataset file at the URL Vite gave it, by its name. */
function stubFetch(fail: (url: string) => boolean = () => false) {
  const mock = vi.fn(async (url: string) => {
    const [, id, file] = url.match(/datasets\/([^/]+)\/(tree|info)\.json/) ?? []
    const text = id ? files[`../../datasets/${id}/${file}.json`] : undefined
    if (!text || fail(url)) return { ok: false, status: 404, json: async () => null }
    return { ok: true, status: 200, json: async () => JSON.parse(text) }
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

async function freshApi() {
  vi.resetModules()
  return import('./api')
}

afterEach(() => vi.unstubAllGlobals())

describe('the registry', () => {
  it('finds every dataset under datasets/, in picker order', async () => {
    const { DATASETS } = await freshApi()
    const ids = DATASETS.map((d) => d.id)
    expect(ids).toEqual(expect.arrayContaining(['maths', 'animals']))
    expect(ids[0]).toBe('maths')
    for (const d of DATASETS) expect(d.manifest.title).toBeTruthy()
  })
})

describe('a round', () => {
  it('plays on the device, fetching the tree once', async () => {
    const mock = stubFetch()
    const api = await freshApi()
    const round = await api.startRound('animals', { seed: undefined })
    const state = await api.fetchGameState('animals', round.secret, [round.secret])
    expect(state?.label).toBe('Animalia')
    await api.fetchSuggestions('animals', 'lion')
    expect(mock.mock.calls.filter(([u]) => String(u).includes('animals/tree')).length).toBe(1)
  })

  it('answers suggestions without waiting once the tree is loaded, and the same as waiting', async () => {
    stubFetch()
    const api = await freshApi()
    expect(api.suggestionsNow('plants', 'rose')).toBeNull()
    await api.startRound('plants')
    const now = api.suggestionsNow('plants', 'rose', 5)
    expect(now?.labels).toEqual(await api.fetchSuggestions('plants', 'rose', 5))
    expect(now?.labels[0]).toBe('Rose')
  })

  it('does not keep a failed download, so the next attempt can succeed', async () => {
    let down = true
    stubFetch(() => down)
    const api = await freshApi()
    await expect(api.startRound('maths')).rejects.toThrow()
    down = false
    await expect(api.startRound('maths')).resolves.toMatchObject({ daily: false })
  })

  it('refuses a seed made on another tree, and says which tree it was', async () => {
    stubFetch()
    const api = await freshApi()
    const { seed } = await api.startRound('maths')
    await expect(api.startRound('animals', { seed })).rejects.toThrow(/different dataset/)
    expect(await api.datasetForSeed(seed)).toBe('maths')
    expect(await api.datasetForSeed('not a seed')).toBeNull()
  })
})

describe('info', () => {
  it("merges the tree's label and rank into the stored text", async () => {
    stubFetch()
    const api = await freshApi()
    const lion = await api.fetchInfo('animals', 'Panthera leo')
    expect(lion).toMatchObject({ label: 'lion', rank: 'Species' })
    expect(lion?.description).toMatch(/lion/i)
    const graphs = await api.fetchInfo('maths', '05Cxx')
    expect(graphs?.label).toBe('Graph theory')
    expect(graphs?.items?.length).toBeGreaterThan(10)
  })

  it('answers null for a name the tree does not hold', async () => {
    stubFetch()
    const api = await freshApi()
    expect(await api.fetchInfo('maths', 'constructor')).toBeNull()
  })
})
