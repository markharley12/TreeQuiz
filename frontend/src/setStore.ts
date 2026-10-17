/**
 * What the set games — odd one out and line-up — keep on the device, each
 * under its own keys: the set in progress on each tree, so a reload resumes
 * it; a tally of finished sets; and the day's set, kept once finished.
 *
 * A set is its seed, so the seed and the answers given are the whole of it;
 * the puzzles are dealt again from the seed. An answer is whatever the game
 * records: odd one out's is the name picked, line-up's the four in order.
 */
import { storageKey } from './engine/datasets'
import { dayBefore, dayText } from './results'

export type SetGame = 'odd' | 'lineup'

export interface SetSession<A> {
  seed: string
  /** One per puzzle answered so far, in order. */
  answers: A[]
  /** For the day's set, which day: `YYYY-MM-DD`. */
  day?: string
}

/** A day's set, finished: kept per tree, first finish only, as dailies of
 *  the guessing game are (see results.ts). */
export interface SetDaily<A> {
  seed: string
  answers: A[]
  /** The set's score: puzzles right, or for line-up, names in place. */
  right: number
}

export interface SetTally {
  sets: number
  /** Every set's score, added up. */
  right: number
  best: number
  /** The last set counted, so a reload at the end does not count it twice. */
  last: string | null
}

const sessionKey = (game: SetGame, dataset: string) => storageKey(game, dataset)
const tallyKey = (game: SetGame, dataset: string) => storageKey(`${game}tally`, dataset)
const dailyKey = (game: SetGame, dataset: string) => storageKey(`${game}daily`, dataset)

function read<T>(key: string, valid: (v: unknown) => v is T): T | null {
  try {
    const raw = localStorage.getItem(key)
    const parsed: unknown = raw ? JSON.parse(raw) : null
    return valid(parsed) ? parsed : null
  } catch {
    return null
  }
}

function write(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Private browsing, or storage full: the set still plays.
  }
}

const isSession = (v: unknown): v is SetSession<unknown> =>
  typeof v === 'object' && v !== null && typeof (v as SetSession<unknown>).seed === 'string' && Array.isArray((v as SetSession<unknown>).answers)

const isTally = (v: unknown): v is SetTally =>
  typeof v === 'object' && v !== null && typeof (v as SetTally).sets === 'number' && typeof (v as SetTally).right === 'number'

export function readSetSession<A>(game: SetGame, dataset: string): SetSession<A> | null {
  return read(sessionKey(game, dataset), isSession) as SetSession<A> | null
}

export function writeSetSession<A>(game: SetGame, dataset: string, session: SetSession<A>): void {
  write(sessionKey(game, dataset), session)
}

export const EMPTY_TALLY: SetTally = { sets: 0, right: 0, best: 0, last: null }

export function readSetTally(game: SetGame, dataset: string): SetTally {
  return read(tallyKey(game, dataset), isTally) ?? EMPTY_TALLY
}

/** Count a finished set, once per seed in a row. Returns the tally after. */
export function recordSet(game: SetGame, dataset: string, seed: string, right: number): SetTally {
  const tally = readSetTally(game, dataset)
  if (tally.last === seed) return tally
  const next = { sets: tally.sets + 1, right: tally.right + right, best: Math.max(tally.best, right), last: seed }
  write(tallyKey(game, dataset), next)
  return next
}

const isDailies = (v: unknown): v is Record<string, SetDaily<unknown>> => typeof v === 'object' && v !== null && !Array.isArray(v)

export function readSetDailies<A>(game: SetGame, dataset: string): Record<string, SetDaily<A>> {
  return (read(dailyKey(game, dataset), isDailies) ?? {}) as Record<string, SetDaily<A>>
}

/** Keep a finished day's set — the first finish only. True if kept. */
export function recordSetDaily<A>(game: SetGame, dataset: string, day: string, record: SetDaily<A>): boolean {
  const all = readSetDailies<A>(game, dataset)
  if (all[day]) return false
  write(dailyKey(game, dataset), { ...all, [day]: record })
  return true
}

/** Days in a row with the day's set finished, up to today — or yesterday,
 *  while today's is still to play. Any score keeps it: a set is not won or
 *  lost, only played. */
export function setStreak(records: Record<string, unknown>, today: string): number {
  let streak = 0
  let day = records[today] ? today : dayBefore(today)
  while (records[day]) {
    streak++
    day = dayBefore(day)
  }
  return streak
}

/** "TreeQuiz · Cities · odd one out", the score, a mark per puzzle, the link.
 *  A day's set says which day. */
export function oddShareText(title: string, marks: boolean[], link: string, day?: string): string {
  const right = marks.filter(Boolean).length
  return [
    `TreeQuiz · ${title} · odd one out${day ? ` · ${dayText(day)}` : ''}`,
    `${right}/${marks.length} ${marks.map((m) => (m ? '✅' : '❌')).join('')}`,
    link,
  ].join('\n')
}

/** "TreeQuiz · Cities · line-up", the score, a row of squares per puzzle —
 *  green where a name was in its place — and the link. Never the names. */
export function lineUpShareText(title: string, places: boolean[][], link: string, day?: string): string {
  const points = places.flat().filter(Boolean).length
  return [
    `TreeQuiz · ${title} · line-up${day ? ` · ${dayText(day)}` : ''}`,
    `${points}/${places.flat().length}`,
    ...places.map((row) => row.map((ok) => (ok ? '🟩' : '🟥')).join('')),
    link,
  ].join('\n')
}
