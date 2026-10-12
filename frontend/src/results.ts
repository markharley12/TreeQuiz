/**
 * A finished round, told without giving the answer away, and the record of
 * every daily played on this device.
 *
 * The result is a row of squares, one per guess in the order made, coloured by
 * how close that guess came — the same warmth the tree is coloured by, cut into
 * four bands. It says how a round went (cold for a while, then a run of warm
 * guesses) and nothing about where the answer is, so it can be posted where
 * people who have not played yet will see it.
 *
 * Dailies are kept per tree, one entry per day, and the entry is the whole
 * finished round rather than a score: the front page reopens today's finished
 * daily from it even after a practice round has replaced the saved session,
 * which would otherwise hand the daily out a second time. Only the first finish
 * of a day is kept, so a replay cannot improve a streak.
 *
 * No game rule lives here — the warmths come from the engine's display tree —
 * so, like `endgame.ts`, this has no Python twin.
 */
import type { TreeNode } from './api'
import { storageKey } from './engine/datasets'

/** One finished daily. */
export interface DailyRecord {
  /** The day's seed, for the link a shared result carries. */
  seed: string
  guesses: string[]
  /** Each guess's warmth with the answer, in the order guessed. */
  warmths: number[]
  hints: number
  hintPoints: number
  won: boolean
}

export type DailyRecords = Record<string, DailyRecord>

/** Warmth bands, coldest first. Four, because four coloured squares are what
 *  every platform's emoji has; the answer itself gets its own mark. */
const BANDS = ['🟥', '🟧', '🟨', '🟩'] as const
export const ANSWER_MARK = '🎯'
export const HINT_MARK = '💡'
/** Squares per line, so a long round wraps as a block rather than one line
 *  that a chat window breaks wherever it likes. */
export const PER_LINE = 10
/** The most squares shown. A bulk guess can spend a hundred guesses at once,
 *  and a hundred squares is not something anybody reads. */
export const MAX_SQUARES = 50

export function square(warmth: number): string {
  if (warmth >= 1) return ANSWER_MARK
  const t = Math.min(Math.max(warmth || 0, 0), 0.9999)
  return BANDS[Math.floor(t * BANDS.length)]
}

/** The squares for a round, `PER_LINE` to a line; past `MAX_SQUARES` the rest
 *  are counted, and the answer's mark is kept at the end if it was found. */
export function squares(warmths: number[]): string {
  let marks = warmths.map(square)
  let tail = ''
  if (marks.length > MAX_SQUARES) {
    const won = marks[marks.length - 1] === ANSWER_MARK
    const keep = marks.slice(0, MAX_SQUARES - (won ? 1 : 0))
    tail = ` +${marks.length - keep.length - (won ? 1 : 0)}`
    marks = won ? [...keep, ANSWER_MARK] : keep
  }
  const lines: string[] = []
  for (let i = 0; i < marks.length; i += PER_LINE) lines.push(marks.slice(i, i + PER_LINE).join(''))
  if (tail) lines[lines.length - 1] += tail
  return lines.join('\n')
}

/** Each guess's warmth with the answer, in the order guessed, read off the
 *  display tree: a guess node carries the warmth of its LCA with the secret.
 *  A guess the tree does not show (it has not loaded yet) counts as cold. */
export function guessWarmths(tree: TreeNode | null, guesses: string[]): number[] {
  const byLabel = new Map<string, number>()
  const walk = (n: TreeNode) => {
    if (n.node_type === 'guess') byLabel.set(n.label, n.lca_warmth ?? 0)
    n.children.forEach(walk)
  }
  if (tree) walk(tree)
  return guesses.map((g) => byLabel.get(g) ?? 0)
}

export interface ShareInput {
  /** The tree's short title: "Cities". */
  title: string
  daily: boolean
  /** `YYYY-MM-DD`, for a daily. */
  day?: string
  warmths: number[]
  hints: number
  hintPoints: number
  won: boolean
  link: string
}

/** "12 Oct 2026", the same in every locale, since the text is for other people. */
export function dayText(isoDay: string): string {
  const [y, m, d] = isoDay.split('-').map(Number)
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  return `${d} ${months[m - 1]} ${y}`
}

/** What a score line says: "7 guesses", "7 guesses + 💡💡 (25)", "gave up after 9". */
export function scoreText(guesses: number, hints: number, hintPoints: number, won: boolean): string {
  const g = `${guesses} ${guesses === 1 ? 'guess' : 'guesses'}`
  if (!won) return `gave up after ${g}`
  return hints > 0 ? `${g} + ${HINT_MARK.repeat(hints)} (${guesses + hintPoints})` : g
}

export function shareText(r: ShareInput): string {
  const when = r.daily && r.day ? dayText(r.day) : 'practice'
  return [
    `TreeQuiz · ${r.title} · ${when}`,
    scoreText(r.warmths.length, r.hints, r.hintPoints, r.won),
    squares(r.warmths),
    r.link,
  ].join('\n')
}

// --- the daily record ---------------------------------------------------------

const recordsKey = (dataset: string) => storageKey('daily', dataset)

/** Every daily played on this tree, by day. Empty when storage is blocked or
 *  holds something unreadable: stats are a nicety, never a reason to fail. */
export function readDailies(dataset: string): DailyRecords {
  try {
    const raw = localStorage.getItem(recordsKey(dataset))
    const parsed = raw ? JSON.parse(raw) : {}
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
  } catch {
    return {}
  }
}

/** Keep a finished daily — the first finish of a day only. True if kept. */
export function recordDaily(dataset: string, day: string, record: DailyRecord): boolean {
  const all = readDailies(dataset)
  if (all[day]) return false
  all[day] = record
  try {
    localStorage.setItem(recordsKey(dataset), JSON.stringify(all))
  } catch {
    return false
  }
  return true
}

export const score = (r: DailyRecord) => r.guesses.length + r.hintPoints

/** Score bands for the histogram. A round takes far more guesses than a
 *  Wordle, and how many depends on the tree, so the bands widen as they go. */
export const BUCKETS: { label: string; max: number }[] = [
  { label: '1–5', max: 5 },
  { label: '6–10', max: 10 },
  { label: '11–15', max: 15 },
  { label: '16–20', max: 20 },
  { label: '21–30', max: 30 },
  { label: '31+', max: Infinity },
]

export function bucketOf(s: number): number {
  return BUCKETS.findIndex((b) => s <= b.max)
}

export interface Stats {
  played: number
  won: number
  /** Wins on consecutive days, up to today — or up to yesterday while today
   *  is still unplayed, so a streak does not read 0 before breakfast. */
  streak: number
  bestStreak: number
  /** Wins per score band, as `BUCKETS`. */
  histogram: number[]
  /** The mean score of wins, or null with none. */
  average: number | null
}

/** The day before an ISO day, by calendar rather than by 24 hours of clock. */
export function dayBefore(isoDay: string): string {
  const d = new Date(`${isoDay}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() - 1)
  return d.toISOString().slice(0, 10)
}

export function computeStats(records: DailyRecords, today: string): Stats {
  const days = Object.keys(records).sort()
  const wins = days.filter((d) => records[d].won)
  const histogram = BUCKETS.map(() => 0)
  for (const d of wins) histogram[bucketOf(score(records[d]))]++

  let best = 0
  let run = 0
  let prev: string | null = null
  for (const d of days) {
    if (!records[d].won) run = 0
    else run = prev !== null && dayBefore(d) === prev && records[prev].won ? run + 1 : 1
    best = Math.max(best, run)
    prev = d
  }

  let streak = 0
  let day = records[today] ? today : dayBefore(today)
  while (records[day]?.won) {
    streak++
    day = dayBefore(day)
  }

  return {
    played: days.length,
    won: wins.length,
    streak,
    bestStreak: best,
    histogram,
    average: wins.length ? wins.reduce((s, d) => s + score(records[d]), 0) / wins.length : null,
  }
}
