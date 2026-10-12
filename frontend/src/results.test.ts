import { beforeEach, describe, expect, it } from 'vitest'
import {
  ANSWER_MARK, BUCKETS, MAX_SQUARES, bucketOf, computeStats, dayBefore, dayText, guessWarmths,
  readDailies, recordDaily, scoreText, shareText, square, squares, type DailyRecord,
} from './results'
import type { TreeNode } from './api'

const won = (n: number, hintPoints = 0): DailyRecord => ({
  seed: 'AAAA-BBBBBB', guesses: Array.from({ length: n }, (_, i) => `g${i}`), warmths: [], hints: hintPoints ? 1 : 0, hintPoints, won: true,
})
const lost = (n: number): DailyRecord => ({ ...won(n), won: false })

describe('the squares', () => {
  it('cut warmth into four bands and mark the answer apart', () => {
    expect([0, 0.2, 0.25, 0.49, 0.5, 0.74, 0.75, 0.99, 1].map(square).join(''))
      .toBe('🟥🟥🟧🟧🟨🟨🟩🟩🎯')
  })

  it('treat a missing warmth as cold rather than painting nothing', () => {
    expect(square(NaN)).toBe('🟥')
    expect(square(-1)).toBe('🟥')
  })

  it('wrap ten to a line', () => {
    const text = squares(Array(23).fill(0))
    expect(text.split('\n').map((l) => [...l].length)).toEqual([10, 10, 3])
  })

  it('count what is past the cap, and keep the winning mark at the end', () => {
    const text = squares([...Array(120).fill(0.3), 1])
    expect(text.endsWith(`${ANSWER_MARK} +71`)).toBe(true)
    expect([...text.replace(/[^🟧🎯]/gu, '')].length).toBe(MAX_SQUARES)
  })
})

describe('the share text', () => {
  const base = { title: 'Cities', warmths: [0, 0.6, 1], hints: 0, hintPoints: 0, won: true, link: 'https://x/?d=cities&seed=AAAA-BBBBBB' }

  it('names the tree and the day, and never the answer', () => {
    const text = shareText({ ...base, daily: true, day: '2026-10-12' })
    expect(text).toBe('TreeQuiz · Cities · 12 Oct 2026\n3 guesses\n🟥🟨🎯\nhttps://x/?d=cities&seed=AAAA-BBBBBB')
  })

  it('says practice for a round that is not the daily', () => {
    expect(shareText({ ...base, daily: false }).split('\n')[0]).toBe('TreeQuiz · Cities · practice')
  })

  it('shows hints and what they cost, and a round given up', () => {
    expect(scoreText(7, 2, 30, true)).toBe('7 guesses + 💡💡 (37)')
    expect(scoreText(1, 0, 0, true)).toBe('1 guess')
    expect(scoreText(9, 0, 0, false)).toBe('gave up after 9 guesses')
  })

  it('writes the day the same way everywhere', () => {
    expect(dayText('2027-01-03')).toBe('3 Jan 2027')
  })
})

describe('reading warmths off the tree', () => {
  const leaf = (label: string, lca: number): TreeNode => ({
    name: label, label, node_type: 'guess', depth: 2, on_secret_path: false, warmth: 1, lca_warmth: lca, children: [],
  })
  const tree: TreeNode = {
    name: 'root', label: 'root', node_type: 'ancestor', depth: 0, on_secret_path: true, warmth: 0,
    children: [leaf('b', 0.5), { ...leaf('a', 0), node_type: 'ancestor', children: [leaf('c', 1)] }],
  }

  it('gives each guess in the order guessed, cold for one not drawn', () => {
    expect(guessWarmths(tree, ['c', 'b', 'missing'])).toEqual([1, 0.5, 0])
    expect(guessWarmths(null, ['c'])).toEqual([0])
  })
})

describe('the daily record', () => {
  beforeEach(() => localStorage.clear())

  it('keeps the first finish of a day only', () => {
    expect(recordDaily('cities', '2026-10-12', won(5))).toBe(true)
    expect(recordDaily('cities', '2026-10-12', won(1))).toBe(false)
    expect(readDailies('cities')['2026-10-12'].guesses).toHaveLength(5)
    expect(readDailies('maths')).toEqual({})
  })

  it('reads anything unreadable as no record at all', () => {
    localStorage.setItem('treequiz:daily:cities', '[1,2]')
    expect(readDailies('cities')).toEqual({})
    localStorage.setItem('treequiz:daily:cities', '{oops')
    expect(readDailies('cities')).toEqual({})
  })
})

describe('the stats', () => {
  it('count calendar days across a month end', () => {
    expect(dayBefore('2026-11-01')).toBe('2026-10-31')
    expect(dayBefore('2028-03-01')).toBe('2028-02-29')
  })

  it('keep a streak alive until today is over, and break it on a gap or a give-up', () => {
    const records = {
      '2026-10-01': won(4), '2026-10-02': won(8), '2026-10-03': lost(12),
      '2026-10-05': won(3), '2026-10-06': won(9), '2026-10-07': won(30),
    }
    // Today unplayed: the streak runs to yesterday.
    expect(computeStats(records, '2026-10-08').streak).toBe(3)
    // A day missed: gone.
    expect(computeStats(records, '2026-10-09').streak).toBe(0)
    const s = computeStats(records, '2026-10-07')
    expect(s).toMatchObject({ played: 6, won: 5, streak: 3, bestStreak: 3 })
    expect(s.average).toBeCloseTo((4 + 8 + 3 + 9 + 30) / 5)
  })

  it('band scores for the histogram, hints included', () => {
    const s = computeStats({ '2026-10-01': won(3), '2026-10-02': won(4, 10), '2026-10-03': won(40) }, '2026-10-03')
    expect(s.histogram).toEqual([1, 0, 1, 0, 0, 1])
    expect(BUCKETS[bucketOf(31)].label).toBe('31+')
  })

  it('are empty with nothing played', () => {
    expect(computeStats({}, '2026-10-12')).toEqual({
      played: 0, won: 0, streak: 0, bestStreak: 0, histogram: [0, 0, 0, 0, 0, 0], average: null,
    })
  })
})
