import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { Info } from './api'

// The cache is module state with no reset, which is right for the app and means
// each case needs a fresh module. `fetchInfo` is the only thing it calls.
const fetchInfo = vi.fn()
vi.mock('./api', () => ({ fetchInfo: (...args: unknown[]) => fetchInfo(...args) }))

async function loadCache() {
  vi.resetModules()
  fetchInfo.mockReset()
  return import('./infoCache')
}

function info(description: string, image = ''): Info {
  return { name: 'x', label: 'x', rank: '', description, image_url: image }
}

afterEach(() => { cleanup() })

describe('cachedInfo', () => {
  it('is undefined until someone asks', async () => {
    // Three states, all meaningful: undefined = nobody asked, null = asked and
    // there is no article, an object = a hit.
    const { cachedInfo } = await loadCache()
    expect(cachedInfo('Aves', 'example')).toBeUndefined()
  })

  it('returns the hit once it lands', async () => {
    const { cachedInfo, loadInfo } = await loadCache()
    fetchInfo.mockResolvedValue(info('birds'))
    await loadInfo('Aves', 'example')
    expect(cachedInfo('Aves', 'example')?.description).toBe('birds')
  })
})

describe('the cache key', () => {
  it('separates the same name in two datasets', async () => {
    // Load-bearing, not tidy: 1,047 names appear in both the example and the
    // scrape, 86% of them with a different description and 68% a different
    // picture. Animalia is 923 characters in one and 3,369 in the other.
    const { cachedInfo, loadInfo } = await loadCache()
    fetchInfo.mockResolvedValueOnce(info('923 chars'))
    fetchInfo.mockResolvedValueOnce(info('3369 chars'))

    await loadInfo('Animalia', 'example')
    await loadInfo('Animalia', 'wikidata-2026-09')

    expect(cachedInfo('Animalia', 'example')?.description).toBe('923 chars')
    expect(cachedInfo('Animalia', 'wikidata-2026-09')?.description).toBe('3369 chars')
    expect(fetchInfo).toHaveBeenCalledTimes(2)
  })

  it('does not let a dataset/name pair collide with another', async () => {
    // Concatenated plainly, ('a', 'bc') and ('ab', 'c') are one key. The
    // separator is a newline, which a dataset name cannot contain.
    const { cachedInfo, loadInfo } = await loadCache()
    fetchInfo.mockResolvedValueOnce(info('first'))
    await loadInfo('bc', 'a')
    expect(cachedInfo('c', 'ab')).toBeUndefined()
  })

  it('passes the dataset through to the API', async () => {
    const { loadInfo } = await loadCache()
    fetchInfo.mockResolvedValue(info('x'))
    await loadInfo('Aves', 'wikidata-2026-09')
    expect(fetchInfo).toHaveBeenCalledWith('wikidata-2026-09', 'Aves')
  })
})

describe('loadInfo', () => {
  it('asks once and serves the rest from memory', async () => {
    const { loadInfo } = await loadCache()
    fetchInfo.mockResolvedValue(info('birds'))

    await loadInfo('Aves', 'example')
    await loadInfo('Aves', 'example')
    await loadInfo('Aves', 'example')

    expect(fetchInfo).toHaveBeenCalledTimes(1)
  })

  it('shares one request between simultaneous callers', async () => {
    // The popup, the hover preview and the thumbnail all want the same node,
    // and they ask in the same tick.
    const { loadInfo } = await loadCache()
    let resolve!: (v: Info) => void
    fetchInfo.mockReturnValue(new Promise((r) => { resolve = r }))

    const all = Promise.all([
      loadInfo('Aves', 'example'),
      loadInfo('Aves', 'example'),
      loadInfo('Aves', 'example'),
    ])
    resolve(info('birds'))
    const [a, b, c] = await all

    expect(fetchInfo).toHaveBeenCalledTimes(1)
    expect(a).toBe(b)
    expect(b).toBe(c)
  })

  it('caches a 404 as firmly as a hit', async () => {
    // ~3% of nodes have no article. Re-asking on every hover is exactly the
    // cost the cache exists to avoid, so "there is nothing" is a real answer.
    const { cachedInfo, loadInfo } = await loadCache()
    fetchInfo.mockResolvedValue(null)

    expect(await loadInfo('Nothing', 'example')).toBeNull()
    expect(await loadInfo('Nothing', 'example')).toBeNull()

    expect(fetchInfo).toHaveBeenCalledTimes(1)
    expect(cachedInfo('Nothing', 'example')).toBeNull()
  })

  it('does not cache a transient failure, so a later hover retries', async () => {
    // The node must not be permanently blank because the network blinked.
    const { cachedInfo, loadInfo } = await loadCache()
    fetchInfo.mockRejectedValueOnce(new Error('network'))

    expect(await loadInfo('Aves', 'example')).toBeNull()
    // Nobody has a real answer yet — distinct from the cached null above.
    expect(cachedInfo('Aves', 'example')).toBeUndefined()

    fetchInfo.mockResolvedValueOnce(info('birds'))
    expect((await loadInfo('Aves', 'example'))?.description).toBe('birds')
    expect(fetchInfo).toHaveBeenCalledTimes(2)
  })

  it('clears the in-flight entry after a failure', async () => {
    // Left behind, the rejected promise would be handed to every later caller
    // and the node could never recover.
    const { loadInfo } = await loadCache()
    fetchInfo.mockRejectedValueOnce(new Error('network'))
    await loadInfo('Aves', 'example')

    fetchInfo.mockResolvedValueOnce(info('birds'))
    await loadInfo('Aves', 'example')
    fetchInfo.mockResolvedValueOnce(info('unused'))
    expect((await loadInfo('Aves', 'example'))?.description).toBe('birds')
  })
})

describe('useInfoCache', () => {
  it('re-renders when something lands, so the thumbnail appears', async () => {
    // A node can only show a picture if something already knows its URL, so the
    // cache landing is what puts it there.
    const { loadInfo, useInfoCache } = await loadCache()
    fetchInfo.mockResolvedValue(info('birds', 'https://example.invalid/a.jpg'))

    const { result } = renderHook(() => useInfoCache())
    const before = result.current

    await act(async () => { await loadInfo('Aves', 'example') })

    expect(result.current).not.toBe(before)
  })

  it('does not re-render for a cache hit, which changed nothing', async () => {
    const { loadInfo, useInfoCache } = await loadCache()
    fetchInfo.mockResolvedValue(info('birds'))
    await loadInfo('Aves', 'example')

    const { result } = renderHook(() => useInfoCache())
    const before = result.current
    await act(async () => { await loadInfo('Aves', 'example') })

    expect(result.current).toBe(before)
  })

  it('does not re-render for a transient failure', async () => {
    const { loadInfo, useInfoCache } = await loadCache()
    fetchInfo.mockRejectedValueOnce(new Error('network'))

    const { result } = renderHook(() => useInfoCache())
    const before = result.current
    await act(async () => { await loadInfo('Aves', 'example') })

    expect(result.current).toBe(before)
  })

  it('stops notifying after unmount', async () => {
    const { loadInfo, useInfoCache } = await loadCache()
    fetchInfo.mockResolvedValue(info('birds'))
    const { unmount } = renderHook(() => useInfoCache())
    unmount()
    await expect(loadInfo('Aves', 'example')).resolves.toBeTruthy()
  })
})
