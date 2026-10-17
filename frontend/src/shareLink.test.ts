import { describe, expect, it } from 'vitest'
import { readLink, shareBase, shareLink, withoutLink } from './shareLink'

describe('shareBase', () => {
  it('links to the page itself, without its query or index.html', () => {
    expect(shareBase('https://x.io/TreeQuiz/index.html?d=maths&seed=OLD#t')).toBe('https://x.io/TreeQuiz/')
  })
})

describe('shareLink and readLink', () => {
  it('round-trip the tree and the seed', () => {
    const link = shareLink('https://x.io/TreeQuiz/', 'maths', 'J3XF-ABC234')
    expect(link).toBe('https://x.io/TreeQuiz/?d=maths&seed=J3XF-ABC234')
    expect(readLink(new URL(link).search)).toStrictEqual({ dataset: 'maths', seed: 'J3XF-ABC234', odd: null, lineup: null })
  })

  it('treat a blank parameter as absent', () => {
    expect(readLink('?d=&seed=%20&odd=')).toStrictEqual({ dataset: null, seed: null, odd: null, lineup: null })
    expect(readLink('')).toStrictEqual({ dataset: null, seed: null, odd: null, lineup: null })
  })

  it('read a seed with no tree, which the engine then places by its tag', () => {
    expect(readLink('?seed=J3XF-ABC234')).toStrictEqual({ dataset: null, seed: 'J3XF-ABC234', odd: null, lineup: null })
  })
})

describe('an odd-one-out link', () => {
  it('carries its seed under its own name, so it opens that game', () => {
    const link = shareLink('https://x.io/', 'cities', 'J3XF-ABC234', 'odd')
    expect(link).toBe('https://x.io/?d=cities&odd=J3XF-ABC234')
    expect(readLink(new URL(link).search)).toStrictEqual({ dataset: 'cities', seed: null, odd: 'J3XF-ABC234', lineup: null })
    expect(withoutLink(link)).toBe('https://x.io/')
  })
})

describe('a line-up link', () => {
  it('carries its seed under its own name too', () => {
    const link = shareLink('https://x.io/', 'plants', 'J3XF-ABC234', 'lineup')
    expect(link).toBe('https://x.io/?d=plants&lineup=J3XF-ABC234')
    expect(readLink(new URL(link).search)).toStrictEqual({ dataset: 'plants', seed: null, odd: null, lineup: 'J3XF-ABC234' })
    expect(withoutLink(link)).toBe('https://x.io/')
  })
})

describe('withoutLink', () => {
  it("takes the link's parameters out and leaves anything else", () => {
    expect(withoutLink('https://x.io/?d=maths&seed=A&utm=1#h')).toBe('https://x.io/?utm=1#h')
  })
})
