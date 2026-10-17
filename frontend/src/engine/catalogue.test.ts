import { describe, expect, it } from 'vitest'
import { downloadSet, formatBytes, sizeOf } from './catalogue'
import catalogue from 'virtual:treequiz-catalogue'

const file = (bytes: number) => ({ url: '', bytes, gzip: bytes / 4 })

describe('what a download fetches', () => {
  it('is the tree and its text, and for a sized tree the tiers up to its default', () => {
    const files = { 'tree.json': file(10), 'info-500.json': file(1), 'info-2000.json': file(2), 'info-5000.json': file(5) }
    const sized = { manifest: { title: 't', sizes: { min: 500, default: 2000 } } as never, files }
    expect(downloadSet(sized)).toEqual(['info-2000.json', 'info-500.json', 'tree.json'])
    expect(sizeOf(sized, downloadSet(sized))).toEqual({ bytes: 13, gzip: 3.25 })
    // A default between stops takes the tier that reaches it.
    const between = { ...sized, manifest: { title: 't', sizes: { default: 1500 } } as never }
    expect(downloadSet(between)).toEqual(['info-2000.json', 'info-500.json', 'tree.json'])
    const unsized = { manifest: { title: 't' }, files }
    expect(downloadSet(unsized)).toHaveLength(4)
    expect(downloadSet({ manifest: { title: 't' }, files: { 'tree.json': file(1), 'info.json': file(1) } })).toEqual(['info.json', 'tree.json'])
    expect(downloadSet({ manifest: { title: 't' }, files: null })).toEqual([])
  })

  it('reads sizes as phones count them', () => {
    expect(formatBytes(820_000)).toBe('820 KB')
    expect(formatBytes(1_260_000)).toBe('1.3 MB')
    expect(formatBytes(45_600_000)).toBe('46 MB')
    expect(formatBytes(12)).toBe('1 KB')
  })
})

describe("the build's catalogue", () => {
  it('lists every tree with a version and the size of every file', () => {
    const maths = catalogue.trees.find((t) => t.id === 'maths')!
    expect(maths.version).toMatch(/^[0-9a-f]{12}$/)
    expect(Object.keys(maths.files!)).toEqual(['info.json', 'tree.json'])
    expect(maths.files!['tree.json'].bytes).toBeGreaterThan(maths.files!['tree.json'].gzip)
    expect(maths.manifest.title).toBeTruthy()
  })
})
