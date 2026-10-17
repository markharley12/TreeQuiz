/**
 * A set game's life on a tree, shared by odd one out and line-up: which set
 * to deal on arrival, answering, moving on, and counting a finished set once.
 *
 * On arrival: a link's set; else a set in progress; else today's set while
 * it is still to play; else the last set, finished. Today's set is the day's
 * seed dealt by the game's own rules, kept first finish only; once finished
 * it reopens on its score rather than being dealt twice. A day's set left
 * from another day plays on as an ordinary one.
 */
import { useEffect, useState } from 'react'
import { normalise, utcToday } from './engine/seed'
import {
  readSetDailies, readSetSession, readSetTally, recordSet, recordSetDaily, writeSetSession,
  type SetDaily, type SetGame, type SetTally,
} from './setStore'

export interface DealtSet<P> {
  seed: string
  puzzles: P[]
}

/** How to deal: a seed, the answers already given, and the day if the set is
 *  a day's. A day with no seed deals that day's set. */
export interface Deal<A> {
  seed?: string
  resumed?: A[]
  /** Reopened from the day's record, so already counted in the tally. */
  counted?: boolean
  day?: string
}

interface Options<P, A> {
  game: SetGame
  dataset: string
  /** A set's seed from a link, to deal instead of resuming. */
  linkSeed: string | null
  size: number
  start: (dataset: string, opts: { seed?: string; daily?: boolean }) => Promise<DealtSet<P>>
  /** What an answer scores: 1 or 0 for odd one out, names in place for line-up. */
  points: (puzzle: P, answer: A) => number
}

export function useSetGame<P, A>({ game, dataset, linkSeed, size, start, points }: Options<P, A>) {
  const [set, setSet] = useState<DealtSet<P> | null>(null)
  const [answers, setAnswers] = useState<A[]>([])
  // The puzzle on screen. Behind `answers` by one while an answer is shown.
  const [shown, setShown] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [tally, setTally] = useState<SetTally>(() => readSetTally(game, dataset))
  // The day this set is for, if it is a day's set; null for any other.
  const [day, setDay] = useState<string | null>(null)
  const [dailies, setDailies] = useState(() => readSetDailies<A>(game, dataset))
  const today = utcToday()

  const scoreOf = (of: DealtSet<P>, given: A[]) => given.reduce((sum, a, i) => sum + points(of.puzzles[i], a), 0)

  function show(next: DealtSet<P>, resumed: A[], forDay: string | null, counted = false) {
    setError(null)
    setSet(next)
    setAnswers(resumed)
    setShown(Math.min(resumed.length, size))
    setDay(forDay)
    writeSetSession(game, dataset, { seed: next.seed, answers: resumed, ...(forDay ? { day: forDay } : {}) })
    if (resumed.length >= size && !counted) finish(next, resumed, forDay)
  }

  const failed = (e: unknown) => setError(e instanceof Error ? e.message : 'Could not deal that set')

  function deal(how: Deal<A> = {}) {
    start(dataset, { seed: how.seed, daily: how.day !== undefined && !how.seed })
      .then((next) => show(next, how.resumed ?? [], how.day ?? null, how.counted), failed)
  }

  /** Today's set: the record of it once finished, else a fresh deal. */
  function todays(): Deal<A> {
    const done: SetDaily<A> | undefined = readSetDailies<A>(game, dataset)[today]
    return done ? { seed: done.seed, resumed: done.answers, day: today, counted: true } : { day: today }
  }

  // Called off, so a remount deals once rather than twice.
  useEffect(() => {
    const saved = readSetSession<A>(game, dataset)
    const savedDay = saved?.day === today ? today : undefined
    const unfinished = saved !== null && saved.answers.length < size
    const how: Deal<A> = linkSeed !== null
      ? { seed: linkSeed, resumed: saved && sameSeed(saved.seed, linkSeed) ? saved.answers : [] }
      : saved && (unfinished || readSetDailies(game, dataset)[today])
        ? { seed: saved.seed, resumed: saved.answers, day: savedDay }
        : todays()
    let cancelled = false
    start(dataset, { seed: how.seed, daily: how.day !== undefined && !how.seed }).then(
      (next) => { if (!cancelled) show(next, how.resumed ?? [], how.day ?? null, how.counted) },
      (e) => { if (!cancelled) failed(e) },
    )
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // A finished set counts toward the tally once per seed, whether it was
  // finished just now or found finished on a reload; a day's set is kept as
  // that day's too.
  function finish(of: DealtSet<P>, given: A[], forDay: string | null) {
    const got = scoreOf(of, given)
    setTally(recordSet(game, dataset, of.seed, got))
    if (forDay) {
      recordSetDaily(game, dataset, forDay, { seed: of.seed, answers: given, right: got })
      setDailies(readSetDailies<A>(game, dataset))
    }
  }

  const puzzle = set && shown < size ? set.puzzles[shown] : null
  const answered = puzzle !== null && answers.length > shown

  function answer(a: A) {
    if (!set || answered || !puzzle) return
    const next = [...answers, a]
    setAnswers(next)
    writeSetSession(game, dataset, { seed: set.seed, answers: next, ...(day ? { day } : {}) })
  }

  function advance() {
    setShown(shown + 1)
    if (set && shown + 1 >= size) finish(set, answers, day)
  }

  return {
    set, answers, shown, error, tally, day, dailies, today, puzzle, answered,
    /** The answer to the puzzle on screen, once given. */
    given: answered ? answers[shown] : null,
    over: set !== null && shown >= size,
    /** Each answered puzzle's points, in order. */
    scores: set ? answers.map((a, i) => points(set.puzzles[i], a)) : [],
    deal, todays, answer, advance,
  }
}

function sameSeed(a: string, b: string): boolean {
  try {
    return normalise(a) === normalise(b)
  } catch {
    return false
  }
}
