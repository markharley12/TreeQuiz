import { describe, expect, it } from 'vitest'
import { makeDataset, type RawNode } from './engine/tree'
import { makeSet } from './engine/lineup'
import { fingerprint } from './engine/seed'
import { leavesOf } from './engine/game'
import { ladder, ordinal } from './lineupReveal'

const n = (name: string, ...children: RawNode[]): RawNode => (children.length ? { name, children } : { name })

// World > Europe > W. Europe > France > IdF > Paris, with one city off each.
const TREE = n('World',
  n('Asia', n('Tokyo'), n('Seoul')),
  n('Europe',
    n('E. Europe', n('Warsaw'), n('Kyiv')),
    n('W. Europe',
      n('Germany', n('Berlin'), n('Munich')),
      n('France', n('Lyon'), n('IdF', n('Paris'), n('Versailles'))))))

describe('the line-up ladder', () => {
  it('runs from where the farthest meets the target down to the target', () => {
    const ds = makeDataset('t', { title: 't' }, TREE)
    const seed = `${fingerprint(leavesOf(ds))}-ABCDEF`
    const p = makeSet(ds, seed).find((x) => x.target === 'Paris' || x.target === 'Versailles')!
    const l = ladder(ds, p)
    expect(l.rungs.map((r) => r.meet.text)).toEqual(['World', 'Europe', 'W. Europe', 'IdF'])
    expect(l.rungs.map((r) => r.place)).toEqual([3, 2, 1, 0])
    // France holds only Lyon besides IdF's two, and Lyon would meet the
    // target at France; IdF was drawn instead, and France is skipped there.
    expect(l.rungs[3].meet.above).toBe('France')
    expect(l.target.text).toBe(p.target)
    expect(l.rungs[0].option.text).toBe(p.order[3])
  })

  it('says places as words', () => {
    expect([0, 1, 2, 3].map(ordinal)).toEqual(['1st', '2nd', '3rd', '4th'])
  })
})
