// @vitest-environment node
/**
 * The TypeScript engine against Python's own answers.
 *
 * `conformance.json` is written by `tests/conformance.py` from the Python
 * engine, and `tests/test_conformance.py` fails if it is stale — so this file
 * passing means the two implementations agree today, not when the port was
 * written. Everything is compared exactly, warmth included: both sides do the
 * same IEEE operations in the same order.
 */
import { describe, expect, it } from 'vitest'
import goldenText from './conformance.json?raw'
import { sha256 } from './sha256'
import { believedLevels, warmthByName } from './ladder'
import { bodyForDate, fingerprint, normalise, resolve } from './seed'
import { getGameState, leavesOf, pick, suggest } from './game'
import { lineage, search, stats, subtree } from './explore'
import { labelOf, ladderFrom, makeDataset, type Dataset, type LadderSpec, type Manifest, type RawNode } from './tree'

type Outcome = { result?: unknown; error?: string }

interface DatasetCases {
  id: string
  warmth: Record<string, number>
  seeds: {
    fingerprint: string
    resolve: ({ seed: string } & Outcome)[]
    daily: { date: string; secret: string }[]
  }
  game: ({ secret: string; guesses: string[]; hints: number } & Outcome)[]
  suggest: { q: string; limit: number; exclude: string[]; result: string[] }[]
  explore: {
    subtree: ({ root: string | null; depth: number | null; budget: number | null } & Outcome)[]
    lineage: ({ name: string } & Outcome)[]
    search: { q: string; limit: number; result: unknown }[]
    stats: unknown
  }
}

interface Golden {
  sha256: { input: string; digest: string }[]
  seeds: {
    fingerprints: { labels: string[]; fingerprint: string }[]
    daily: { date: string; body: string }[]
    normalise: ({ input: string } & Outcome)[]
  }
  ladder: { ladder: LadderSpec | null; tree: RawNode; believed: Record<string, number | null>; warmth: Record<string, number> }[]
  datasets: DatasetCases[]
}

const golden: Golden = JSON.parse(goldenText)

const files = import.meta.glob<string>('../../../datasets/*/{manifest,tree}.json', { eager: true, query: '?raw', import: 'default' })
function dataset(id: string): Dataset {
  const read = (file: string) => {
    const text = files[`../../../datasets/${id}/${file}`]
    if (text === undefined) throw new Error(`dataset ${id} has no ${file}`)
    return JSON.parse(text)
  }
  return makeDataset(id, read('manifest.json') as Manifest, read('tree.json') as RawNode)
}

const expected = (c: Outcome): Outcome => ('error' in c ? { error: c.error } : { result: c.result })
function outcome(fn: () => unknown): Outcome {
  try {
    return { result: fn() }
  } catch (e) {
    return { error: (e as Error).message }
  }
}
const hex = (bytes: Uint8Array) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
const named = (tree: RawNode, values: Map<RawNode, number | null>) => {
  const out: Record<string, number | null> = {}
  const walk = (n: RawNode) => {
    out[n.name] = values.get(n) as number | null
    for (const c of n.children ?? []) walk(c)
  }
  walk(tree)
  return out
}

describe('sha256', () => {
  it.each(golden.sha256.map((c) => [c.input.length, c]))('matches hashlib on a %i-character input', (_, c) => {
    expect(hex(sha256(new TextEncoder().encode(c.input)))).toBe(c.digest)
  })
})

describe('seeds', () => {
  it.each(golden.seeds.fingerprints)('fingerprints $labels', ({ labels, fingerprint: fp }) => {
    expect(fingerprint(labels.map((name) => ({ name })))).toBe(fp)
  })
  it.each(golden.seeds.daily)('derives the daily body for $date', ({ date, body }) => {
    expect(bodyForDate(date)).toBe(body)
  })
  it.each(golden.seeds.normalise)('normalises $input', (c) => {
    expect(outcome(() => normalise(c.input))).toStrictEqual(expected(c))
  })
})

describe('ladder', () => {
  it.each(golden.ladder.map((c, i) => [i, c]))('synthetic tree %i: believed levels and warmth', (_, c) => {
    const ladder = ladderFrom(c.ladder)
    expect(named(c.tree, believedLevels(c.tree, ladder))).toStrictEqual(c.believed)
    expect(Object.fromEntries(warmthByName(c.tree, ladder))).toStrictEqual(c.warmth)
  })
})

describe.each(golden.datasets.map((c) => [c.id, c] as const))('dataset %s', (id, c) => {
  const ds = dataset(id)

  it('gives every node the warmth Python gives it, to the last bit', () => {
    expect(Object.fromEntries(warmthByName(ds.tree, ds.ladder))).toStrictEqual(c.warmth)
  })

  it('fingerprints, resolves seeds and picks dailies as Python does', () => {
    const lv = leavesOf(ds)
    expect(fingerprint(lv)).toBe(c.seeds.fingerprint)
    for (const r of c.seeds.resolve) expect(outcome(() => labelOf(resolve(r.seed, lv)))).toStrictEqual(expected(r))
    for (const d of c.seeds.daily) expect(pick(ds, { daily: true, today: d.date }).secret).toBe(d.secret)
  })

  it.each(c.game.map((r, i) => [i, r]))('round %i draws the same tree', (_, r) => {
    expect(outcome(() => getGameState(ds, r.secret, r.guesses, r.hints))).toStrictEqual(expected(r))
  })

  it('suggests the same names in the same order', () => {
    for (const s of c.suggest) expect(suggest(ds, s.q, s.limit, s.exclude)).toStrictEqual(s.result)
  })

  it('slices, lineages, searches and counts the same', () => {
    for (const s of c.explore.subtree) {
      expect(outcome(() => subtree(ds, s.root, s.depth, s.budget))).toStrictEqual(expected(s))
    }
    for (const l of c.explore.lineage) expect(outcome(() => lineage(ds, l.name))).toStrictEqual(expected(l))
    for (const s of c.explore.search) expect(search(ds, s.q, s.limit)).toStrictEqual(s.result)
    expect(stats(ds)).toStrictEqual(c.explore.stats)
  })
})

it('covers every dataset that ships', () => {
  const shipped = new Set(Object.keys(files).filter((p) => p.endsWith('/tree.json')).map((p) => p.split('/').slice(-2)[0]))
  expect(new Set(golden.datasets.map((c) => c.id))).toStrictEqual(shipped)
})
