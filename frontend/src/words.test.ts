import { describe, expect, it } from 'vitest'
import { DATASETS } from './engine/datasets'
import { infoSource } from './words'

describe('infoSource', () => {
  it('credits the popup text to the source info_source names, not the first listed', () => {
    // The tree's source comes first and has a licence of its own; the popup
    // text is Wikipedia's. Taking the first licence credited it to Glottolog.
    const m = {
      title: 'Languages',
      info_source: 'Wikipedia',
      sources: [
        { name: 'Glottolog 5.3', url: 'https://glottolog.org', licence: 'CC BY 4.0' },
        { name: 'Wikipedia', url: 'https://en.wikipedia.org', licence: 'CC BY-SA 4.0' },
      ],
    }
    expect(infoSource(m)?.licence).toBe('CC BY-SA 4.0')
  })

  it('matches a source whose name starts with info_source, ignoring case', () => {
    const m = { title: 'Maths', info_source: 'msc2020', sources: [{ name: 'MSC2020 — Mathematics Subject Classification', url: '', licence: 'CC BY-NC-SA 4.0' }] }
    expect(infoSource(m)?.licence).toBe('CC BY-NC-SA 4.0')
  })

  it('falls back to the first licensed source when info_source names none', () => {
    const m = { title: 'X', sources: [{ name: 'A', url: '' }, { name: 'B', url: '', licence: 'CC0' }] }
    expect(infoSource(m)?.name).toBe('B')
  })

  it('finds the named source in every shipped dataset that has popups', () => {
    for (const { id, manifest } of DATASETS) {
      if (!manifest.info_source) continue
      const s = infoSource(manifest)
      expect(s?.name.toLowerCase().startsWith(manifest.info_source.toLowerCase()), id).toBe(true)
      expect(s?.licence, id).toBeTruthy()
    }
  })
})
