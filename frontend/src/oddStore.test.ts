import { beforeEach, describe, expect, it } from 'vitest'
import {
  EMPTY_TALLY, oddShareText, oddStreak, readOddDailies, readOddSession, readOddTally, recordOddDaily, recordOddSet, writeOddSession,
} from './oddStore'

beforeEach(() => localStorage.clear())

describe('the odd-one-out store', () => {
  it('keeps each tree its own set in progress', () => {
    writeOddSession('cities', { seed: 'AAAA-BBBBBB', answers: ['Paris'] })
    expect(readOddSession('cities')).toEqual({ seed: 'AAAA-BBBBBB', answers: ['Paris'] })
    expect(readOddSession('maths')).toBeNull()
  })

  it('reads something unreadable as no set at all', () => {
    localStorage.setItem('treequiz:odd:cities', '{"seed": 3}')
    expect(readOddSession('cities')).toBeNull()
    localStorage.setItem('treequiz:odd:cities', 'nope')
    expect(readOddSession('cities')).toBeNull()
  })

  it('counts a finished set once, however often it is reloaded', () => {
    expect(readOddTally('cities')).toEqual(EMPTY_TALLY)
    recordOddSet('cities', 'AAAA-BBBBBB', 7)
    recordOddSet('cities', 'AAAA-BBBBBB', 7)
    expect(recordOddSet('cities', 'AAAA-CCCCCC', 9)).toEqual({ sets: 2, right: 16, best: 9, last: 'AAAA-CCCCCC' })
  })

  it('shares a mark per puzzle and the link, never the names', () => {
    expect(oddShareText('Cities', [true, false, true], 'https://x/?d=cities&odd=A'))
      .toBe('TreeQuiz · Cities · odd one out\n2/3 ✅❌✅\nhttps://x/?d=cities&odd=A')
    expect(oddShareText('Cities', [true], 'L', '2026-10-12').split('\n')[0]).toBe('TreeQuiz · Cities · odd one out · 12 Oct 2026')
  })

  it("keeps the first finish of a day's set, and counts days in a row", () => {
    const rec = { seed: 'AAAA-BBBBBB', answers: [], right: 6 }
    expect(recordOddDaily('cities', '2026-10-11', rec)).toBe(true)
    expect(recordOddDaily('cities', '2026-10-11', { ...rec, right: 10 })).toBe(false)
    recordOddDaily('cities', '2026-10-10', rec)
    recordOddDaily('cities', '2026-10-08', rec)
    const all = readOddDailies('cities')
    expect(all['2026-10-11'].right).toBe(6)
    expect(oddStreak(all, '2026-10-12')).toBe(2)     // today still to play
    expect(oddStreak(all, '2026-10-11')).toBe(2)
    expect(oddStreak(all, '2026-10-13')).toBe(0)
  })
})
