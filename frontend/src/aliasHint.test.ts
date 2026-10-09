import { describe, expect, it } from 'vitest'
import { matchedAliases } from './aliasHint'
import { suggest } from './engine/game'
import { makeDataset, type RawNode } from './engine/tree'

const tree: RawNode = {
  name: 'root',
  children: [
    { name: 'violin', aliases: ['fiddle'] },
    { name: 'fiddle' },
    { name: 'xylophone', aliases: ['strohfiedel', 'straw fiddle', 'fiddlesticks'] },
    { name: 'erhu', aliases: ['Chinese fiddle'] },
  ],
}
const ds = makeDataset('t', { title: 'T' }, tree)

describe('matchedAliases', () => {
  it('names the alias behind every suggestion its own name does not explain', () => {
    const offered = suggest(ds, 'fiddle')
    expect(offered).toStrictEqual(['fiddle', 'violin', 'xylophone', 'erhu'])
    const hints = matchedAliases(ds, 'fiddle', offered)
    expect(hints.has('fiddle')).toBe(false)
    expect(hints.get('violin')).toBe('fiddle')
    expect(hints.get('erhu')).toBe('Chinese fiddle')
  })

  it('picks the alias suggest ranked it by, not the first that matches', () => {
    // "fiddlesticks" matches only as a word start (tier 3); "straw fiddle"
    // ends in the word (tier 1), which is why the xylophone was offered.
    expect(matchedAliases(ds, 'fiddle', ['xylophone']).get('xylophone')).toBe('straw fiddle')
  })

  it('says nothing about labels it was not asked about', () => {
    expect([...matchedAliases(ds, 'fiddle', ['violin']).keys()]).toStrictEqual(['violin'])
  })
})
