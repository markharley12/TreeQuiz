import { beforeEach, describe, expect, it } from 'vitest'
import {
  EMPTY_TALLY, lineUpShareText, oddShareText, readSetDailies, readSetSession, readSetTally, recordSet, recordSetDaily,
  setStreak, writeSetSession,
} from './setStore'

beforeEach(() => localStorage.clear())

describe('the set games store', () => {
  it('keeps each tree and each game its own set in progress', () => {
    writeSetSession('odd', 'cities', { seed: 'AAAA-BBBBBB', answers: ['Paris'] })
    expect(readSetSession('odd', 'cities')).toEqual({ seed: 'AAAA-BBBBBB', answers: ['Paris'] })
    expect(readSetSession('odd', 'maths')).toBeNull()
    expect(readSetSession('lineup', 'cities')).toBeNull()
  })

  it('keeps the keys odd one out has always used', () => {
    writeSetSession('odd', 'cities', { seed: 'S', answers: [] })
    recordSet('odd', 'cities', 'S', 3)
    recordSetDaily('odd', 'cities', '2026-10-11', { seed: 'S', answers: [], right: 3 })
    expect(Object.keys(localStorage).sort()).toEqual(['treequiz:odd:cities', 'treequiz:odddaily:cities', 'treequiz:oddtally:cities'])
  })

  it('reads something unreadable as no set at all', () => {
    localStorage.setItem('treequiz:odd:cities', '{"seed": 3}')
    expect(readSetSession('odd', 'cities')).toBeNull()
    localStorage.setItem('treequiz:odd:cities', 'nope')
    expect(readSetSession('odd', 'cities')).toBeNull()
  })

  it('counts a finished set once, however often it is reloaded', () => {
    expect(readSetTally('lineup', 'cities')).toEqual(EMPTY_TALLY)
    recordSet('lineup', 'cities', 'AAAA-BBBBBB', 14)
    recordSet('lineup', 'cities', 'AAAA-BBBBBB', 14)
    expect(recordSet('lineup', 'cities', 'AAAA-CCCCCC', 18)).toEqual({ sets: 2, right: 32, best: 18, last: 'AAAA-CCCCCC' })
    expect(readSetTally('odd', 'cities')).toEqual(EMPTY_TALLY)
  })

  it("keeps the first finish of a day's set, and counts days in a row", () => {
    const rec = { seed: 'AAAA-BBBBBB', answers: [], right: 6 }
    expect(recordSetDaily('odd', 'cities', '2026-10-11', rec)).toBe(true)
    expect(recordSetDaily('odd', 'cities', '2026-10-11', { ...rec, right: 10 })).toBe(false)
    recordSetDaily('odd', 'cities', '2026-10-10', rec)
    recordSetDaily('odd', 'cities', '2026-10-08', rec)
    const all = readSetDailies('odd', 'cities')
    expect(all['2026-10-11'].right).toBe(6)
    expect(setStreak(all, '2026-10-12')).toBe(2)     // today still to play
    expect(setStreak(all, '2026-10-11')).toBe(2)
    expect(setStreak(all, '2026-10-13')).toBe(0)
  })
})

describe('sharing a set', () => {
  it('shares a mark per odd-one-out puzzle and the link, never the names', () => {
    expect(oddShareText('Cities', [true, false, true], 'https://x/?d=cities&odd=A'))
      .toBe('TreeQuiz · Cities · odd one out\n2/3 ✅❌✅\nhttps://x/?d=cities&odd=A')
    expect(oddShareText('Cities', [true], 'L', '2026-10-12').split('\n')[0]).toBe('TreeQuiz · Cities · odd one out · 12 Oct 2026')
  })

  it('shares a line-up as a row of squares per puzzle', () => {
    expect(lineUpShareText('Plants', [[true, true, true, true], [false, true, false, true]], 'L', '2026-10-12'))
      .toBe('TreeQuiz · Plants · line-up · 12 Oct 2026\n6/8\n🟩🟩🟩🟩\n🟥🟩🟥🟩\nL')
  })
})
