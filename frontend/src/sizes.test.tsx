/**
 * A sized tree in the app: the game's name, the size remembered per tree,
 * the cut loaded once a size, and on the front page the slider, rounds kept
 * per size, and the daily always at the default.
 *
 * No shipped tree is sized (animals-full's files live in a release, not in
 * git), so the registry is stubbed with one that is, beside one that is not.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { Dataset, Manifest, RawNode } from './engine/tree'

const loadDataset = vi.fn()
const startRound = vi.fn()
const startOddSet = vi.fn()

const SIZES = { min: 500, default: 2000, stops: [500, 1000, 2000] }
const ENTRIES = [
  { id: 'trees', hasInfo: false, manifest: { title: 'Trees', short_title: 'Trees', noun: 'tree', noun_plural: 'trees', prompt: 'Guess the tree.', sizes: SIZES } as Manifest },
  { id: 'plain', hasInfo: false, manifest: { title: 'Plain', short_title: 'Plain', noun: 'leaf', noun_plural: 'leaves', prompt: 'Guess the leaf.' } as Manifest },
]

vi.mock('./engine/datasets', async (importOriginal) => {
  const real = await importOriginal<typeof import('./engine/datasets')>()
  return {
    ...real,
    DATASETS: ENTRIES,
    DEFAULT_DATASET: 'trees',
    entryFor: (id: string) => ENTRIES.find((e) => e.id === id),
    loadDataset: (id: string) => loadDataset(id),
    loadedDataset: () => undefined,
  }
})

vi.mock('./api', () => ({
  startRound: (...a: unknown[]) => startRound(...a),
  fetchGameState: async () => null,
  datasetForSeed: async () => null,
  startOddSet: (...a: unknown[]) => startOddSet(...a),
  fetchOddReveal: () => new Promise(() => {}),
  startLineUp: () => new Promise(() => {}),
  fetchLineUpLadder: () => new Promise(() => {}),
}))
vi.mock('./components/GameTree', () => ({ default: () => <div data-testid="game-tree" /> }))
vi.mock('./components/ExploreTree', () => ({ default: () => <div data-testid="explore-tree" /> }))
vi.mock('./components/GuessInput', () => ({ default: () => <div data-testid="guess-input" /> }))

const today = () => new Date().toISOString().slice(0, 10)
const playOn = (dataset: string, sizes: Record<string, unknown> = {}) =>
  localStorage.setItem('treequiz:settings', JSON.stringify({ dataset, sizes }))

beforeEach(() => {
  localStorage.clear()
  playOn('trees')
  startRound.mockImplementation(async (game: string, opts: { daily?: boolean }) =>
    ({ secret: 'oak', seed: game.endsWith('@2000') ? 'AAAA-234567' : 'BBBB-234567', daily: Boolean(opts.daily) }))
  startOddSet.mockImplementation(async () => ({ seed: 'CCCC-234567', puzzles: [] }))
  vi.resetModules()
})

afterEach(cleanup)

describe('a game’s name', () => {
  it('is the tree alone when unsized, and the tree at its size otherwise', async () => {
    const { gameId, parseGame, treeOf } = await import('./sizes')
    expect(gameId('maths', null)).toBe('maths')
    expect(gameId('trees', 500)).toBe('trees@500')
    expect(parseGame('trees@500')).toStrictEqual({ id: 'trees', size: 500 })
    expect(parseGame('trees@all')).toStrictEqual({ id: 'trees', size: 'all' })
    expect(parseGame('maths')).toStrictEqual({ id: 'maths', size: null })
    expect(treeOf('trees@all')).toBe('trees')
  })
})

describe('the size played', () => {
  it('takes only a stop or all, from a link or from storage', async () => {
    const { validSize } = await import('./sizes')
    expect(validSize('trees', '1000')).toBe(1000)
    expect(validSize('trees', 1000)).toBe(1000)
    expect(validSize('trees', 'all')).toBe('all')
    for (const bad of ['1500', 1500, '1e3', '', null, undefined, ' 500']) expect(validSize('trees', bad)).toBeNull()
    expect(validSize('plain', '500')).toBeNull()
  })

  it('is the one last chosen, else the default; none for an unsized tree', async () => {
    const { chooseSize, chosenSize, dailyGame } = await import('./sizes')
    expect(chosenSize('trees')).toBe(2000)
    chooseSize('trees', 'all')
    expect(chosenSize('trees')).toBe('all')
    expect(chosenSize('trees', { trees: 1500 })).toBe(2000)
    expect(chosenSize('plain')).toBeNull()
    expect(dailyGame('trees')).toBe('trees@2000')
    expect(dailyGame('plain')).toBe('plain')
  })

  it('reads on a log scale, with the whole tree a doubling past the last stop', async () => {
    const { sliderMarks } = await import('./sizes')
    const marks = sliderMarks(SIZES)
    expect(marks.map((m) => m.label)).toStrictEqual(['500', '1k', '2k', 'All'])
    expect(marks.map((m) => m.size)).toStrictEqual([500, 1000, 2000, 'all'])
    expect(marks[1].value - marks[0].value).toBeCloseTo(marks[3].value - marks[2].value)
  })
})

describe('loading a game', () => {
  const f = (name: string, fame: number): RawNode => ({ name, fame })
  const TREE: RawNode = { name: 'root', children: [{ name: 'g', children: [f('a', 3), f('b', 2)] }, f('c', 1)] }

  it('cuts the tree to the size, once a size, and plays the whole tree at all', async () => {
    const { makeDataset } = await import('./engine/tree')
    const whole: Dataset = makeDataset('trees', ENTRIES[0].manifest, TREE)
    loadDataset.mockResolvedValue(whole)
    const { loadGame } = await import('./sizes')
    const two = await loadGame('trees@2')
    expect(two.tree).toStrictEqual({ name: 'root', children: [{ name: 'g', children: [f('a', 3), f('b', 2)] }] })
    expect(two.manifest).toBe(whole.manifest)
    expect(await loadGame('trees@2')).toBe(two)
    expect(await loadGame('trees@all')).toBe(whole)
    expect(await loadGame('trees@3')).toBe(whole)
    expect(loadDataset).toHaveBeenCalledWith('trees')
  })
})

describe('the info tiers a size needs', () => {
  it('are every tier up to the first that holds the whole cut', async () => {
    const { tiersUpTo } = await vi.importActual<typeof import('./engine/datasets')>('./engine/datasets')
    const tiers = [500, 1000, 2000, 41153].map((n) => ({ n }))
    expect(tiersUpTo(tiers, 500).map((t) => t.n)).toStrictEqual([500])
    expect(tiersUpTo(tiers, 2000).map((t) => t.n)).toStrictEqual([500, 1000, 2000])
    expect(tiersUpTo(tiers, 1500).map((t) => t.n)).toStrictEqual([500, 1000, 2000])
    expect(tiersUpTo(tiers).map((t) => t.n)).toStrictEqual([500, 1000, 2000, 41153])
    expect(tiersUpTo([], 500)).toStrictEqual([])
  })
})

async function renderApp() {
  const { default: App } = await import('./App')
  return render(<App />)
}

describe('the front page of a sized tree', () => {
  it('has a slider at the size played, and an unsized tree has none', async () => {
    await renderApp()
    const slider = screen.getByRole('slider', { name: 'How many to play with' })
    expect(slider.getAttribute('aria-valuetext')).toBe('2,000')
    expect(screen.getByText('The 2,000 best-known trees.')).toBeTruthy()
    cleanup()
    playOn('plain')
    vi.resetModules()
    await renderApp()
    expect(screen.queryByRole('slider')).toBeNull()
  })

  it('keeps the size chosen, and plays a round of that size under its own key', async () => {
    await renderApp()
    fireEvent.keyDown(screen.getByRole('slider'), { key: 'ArrowLeft' })
    await waitFor(() => expect(screen.getByText(/The 1,000 best-known trees\. Today’s is always from the 2,000\./)).toBeTruthy())
    expect(JSON.parse(localStorage.getItem('treequiz:settings')!).sizes).toStrictEqual({ trees: 1000 })
    fireEvent.click(screen.getByRole('button', { name: 'Practice' }))
    await waitFor(() => expect(startRound).toHaveBeenCalledWith('trees@1000', { daily: false, seed: undefined }))
    await waitFor(() => expect(localStorage.getItem('treequiz:session:trees@1000')).toContain('BBBB-234567'))
    expect(screen.getByText('Practice · 1k')).toBeTruthy()
    expect(localStorage.getItem('treequiz:session:trees@2000')).toBeNull()
  })

  it('plays today’s round at the default size, whatever size is chosen', async () => {
    playOn('trees', { trees: 500 })
    await renderApp()
    fireEvent.click(screen.getByRole('button', { name: /Today’s tree/ }))
    await waitFor(() => expect(startRound).toHaveBeenCalledWith('trees@2000', { daily: true, seed: undefined }))
    expect(await screen.findByText('Daily · 2k')).toBeTruthy()
    expect(JSON.parse(localStorage.getItem('treequiz:settings')!).sizes).toStrictEqual({ trees: 2000 })
  })

  it('shows today’s round as done at any size once the default size has it', async () => {
    playOn('trees', { trees: 500 })
    localStorage.setItem('treequiz:daily:trees@2000', JSON.stringify({
      [today()]: { seed: 'AAAA-234567', guesses: ['oak'], warmths: [1], hints: 0, hintPoints: 0, won: true },
    }))
    await renderApp()
    expect(screen.getByRole('button', { name: 'Today’s tree ✓' })).toBeTruthy()
  })

  it('deals no today’s set away from the default size', async () => {
    playOn('trees', { trees: 500 })
    await renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Odd one out' }))
    await waitFor(() => expect(startOddSet).toHaveBeenCalledWith('trees@500', { seed: undefined, daily: false }))
    expect(screen.queryByRole('button', { name: /Today’s set/ })).toBeNull()
  })

  it('deals today’s set at the default size', async () => {
    await renderApp()
    fireEvent.click(screen.getByRole('button', { name: 'Odd one out' }))
    await waitFor(() => expect(startOddSet).toHaveBeenCalledWith('trees@2000', { seed: undefined, daily: true }))
  })
})
