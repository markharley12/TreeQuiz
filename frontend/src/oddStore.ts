/**
 * What odd one out keeps on the device: the set in progress on each tree, so
 * a reload resumes it, and a tally of finished sets.
 *
 * A set is its seed, so the seed and the answers given are the whole of it;
 * the puzzles are dealt again from the seed.
 */
import { storageKey } from './engine/datasets'

export interface OddSession {
  seed: string
  /** The name picked for each puzzle answered so far, in order. */
  answers: string[]
}

export interface OddTally {
  sets: number
  right: number
  best: number
  /** The last set counted, so a reload at the end does not count it twice. */
  last: string | null
}

const sessionKey = (dataset: string) => storageKey('odd', dataset)
const tallyKey = (dataset: string) => storageKey('oddtally', dataset)

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

const isSession = (v: unknown): v is OddSession =>
  typeof v === 'object' && v !== null && typeof (v as OddSession).seed === 'string' && Array.isArray((v as OddSession).answers)

const isTally = (v: unknown): v is OddTally =>
  typeof v === 'object' && v !== null && typeof (v as OddTally).sets === 'number' && typeof (v as OddTally).right === 'number'

export function readOddSession(dataset: string): OddSession | null {
  return read(sessionKey(dataset), isSession)
}

export function writeOddSession(dataset: string, session: OddSession): void {
  write(sessionKey(dataset), session)
}

export const EMPTY_TALLY: OddTally = { sets: 0, right: 0, best: 0, last: null }

export function readOddTally(dataset: string): OddTally {
  return read(tallyKey(dataset), isTally) ?? EMPTY_TALLY
}

/** Count a finished set, once per seed in a row. Returns the tally after. */
export function recordOddSet(dataset: string, seed: string, right: number): OddTally {
  const tally = readOddTally(dataset)
  if (tally.last === seed) return tally
  const next = { sets: tally.sets + 1, right: tally.right + right, best: Math.max(tally.best, right), last: seed }
  write(tallyKey(dataset), next)
  return next
}

/** "TreeQuiz · Cities · odd one out", the score, a mark per puzzle, the link. */
export function oddShareText(title: string, marks: boolean[], link: string): string {
  const right = marks.filter(Boolean).length
  return [
    `TreeQuiz · ${title} · odd one out`,
    `${right}/${marks.length} ${marks.map((m) => (m ? '✅' : '❌')).join('')}`,
    link,
  ].join('\n')
}
