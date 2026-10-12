import { describe, expect, it } from 'vitest'
import { makeDataset, type Manifest, type RawNode } from './engine/tree'
import type { Puzzle } from './engine/odd'
import { because, reveal } from './oddReveal'

const n = (name: string, children?: RawNode[], extra: Partial<RawNode> = {}): RawNode =>
  ({ name, ...extra, ...(children ? { children } : {}) })

const WORLD = n('World', [
  n('Europe', [n('Western Europe', [
    n('France', [n('Île-de-France', [n('Paris'), n('Versailles')]), n('Lyon')], { rank: 'Country' }),
    n('Germany', [n('Berlin'), n('Hamburg')], { rank: 'Country' }),
  ])]),
  n('Asia', [n('Tokyo'), n('Osaka')]),
])
const group = (name: string, warmth = 0) => ({ name, label: name, rank: '', warmth })
const puzzle = (pair: [string, string], odd: string, g: string, s: string): Puzzle =>
  ({ choices: [...pair, odd], pair, odd, group: group(g), shared: group(s), tier: 0 })

describe('the reveal', () => {
  const ds = makeDataset('w', { title: 'W' }, WORLD)

  it('draws the five nodes that matter and says what each skips', () => {
    const r = reveal(ds, puzzle(['Paris', 'Lyon'], 'Berlin', 'France', 'Western Europe'))
    expect(r.shared).toMatchObject({ text: 'Western Europe', above: 'Europe' })
    expect(r.group).toMatchObject({ text: 'France', above: '', rank: 'Country' })
    expect(r.pair.map((b) => [b.text, b.above])).toEqual([['Paris', 'Île-de-France'], ['Lyon', '']])
    expect(r.odd).toMatchObject({ text: 'Berlin', above: 'Germany' })
  })

  it('shows the root when that is where the three meet', () => {
    const r = reveal(ds, puzzle(['Tokyo', 'Osaka'], 'Paris', 'Asia', 'World'))
    expect(r.shared).toMatchObject({ text: 'World', above: '' })
    expect(r.odd.above).toBe('… › Western Europe › France › Île-de-France')
  })

  it('says why in one sentence', () => {
    const p = puzzle(['Paris', 'Lyon'], 'Berlin', 'France', 'Western Europe')
    expect(because(p, reveal(ds, p), (l) => l)).toBe('Paris and Lyon share France; Berlin meets them only at Western Europe.')
  })

  it('reads a tree of moves as moves', () => {
    const manifest: Manifest = { title: 'Chess', chain_order: 'root_first', chain_trim: '^[0-9]+…' }
    const chess = makeDataset('c', manifest, n('Start', [
      n('1.e4', [n('1…c5', [
        n('2.Nf3', [n('2…d6', [n('Najdorf'), n('Dragon')]), n('2…Nc6', [n('Rossolimo')])]),
        n('2.c3', [n('Alapin')]),
      ])]),
    ]))
    const p = puzzle(['Najdorf', 'Dragon'], 'Rossolimo', '2…d6', '2.Nf3')
    const r = reveal(chess, p)
    expect(r.shared.text).toBe('1.e4 c5 2.Nf3')
    expect(r.group.text).toBe('2…d6')
    expect(r.odd).toMatchObject({ text: 'Rossolimo', above: '2…Nc6' })
    expect(because(p, r, (l) => l)).toBe('Najdorf and Dragon share 1.e4 c5 2.Nf3 d6; Rossolimo meets them only at 1.e4 c5 2.Nf3.')
  })
})
