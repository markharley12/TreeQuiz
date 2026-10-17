/**
 * A sized tree in the app: which size is played, and what follows from it.
 *
 * A tree whose manifest has `sizes` is played cut to its best-known leaves
 * (engine/size.ts), and **the size is part of the game**: a round dealt at
 * 2,000 is not one at 5,000, so everything kept on the device is kept per
 * tree and size. That is done by naming a game `<tree>@<size>` — `animals-
 * full@2000`, `animals-full@all` — and handing that name to everything that
 * used to take a tree's id: the storage keys, the info cache, the API. An
 * unsized tree's game is its id alone, so its keys are what they always were.
 *
 * The daily is the exception that keeps a daily a daily: it is always dealt
 * at the manifest's default size, so everyone plays the same one, and its
 * records live under that size's game.
 */
import { createContext, useContext } from 'react'
import { entryFor, loadDataset, loadedDataset } from './engine/datasets'
import { cut, sizesOf, type Sizes } from './engine/size'
import { makeDataset, type Dataset } from './engine/tree'
import { getSettings, setSetting, useSettings, type Size } from './settings'
import { gameId, parseGame } from './gameId'

export type { Size } from './settings'
export { gameId, parseGame, treeOf } from './gameId'

export function sizesFor(id: string): Sizes | null {
  const entry = entryFor(id)
  return entry ? sizesOf(entry.manifest) : null
}

/** A size from a link or from storage, if the tree offers it: one of its
 *  stops, or `all`. Anything else is null, so a link cannot make a size up. */
export function validSize(id: string, raw: unknown): Size | null {
  const sizes = sizesFor(id)
  if (!sizes) return null
  if (raw === 'all') return 'all'
  const n = typeof raw === 'number' ? raw : typeof raw === 'string' && /^\d+$/.test(raw) ? Number(raw) : NaN
  return sizes.stops.includes(n) ? n : null
}

/** The size a tree is played at: the one last chosen, else its default.
 *  Null for an unsized tree. */
export function chosenSize(id: string, chosen = getSettings().sizes): Size | null {
  const sizes = sizesFor(id)
  if (!sizes) return null
  return validSize(id, Object.prototype.hasOwnProperty.call(chosen, id) ? chosen[id] : null) ?? sizes.default
}

export function chooseSize(id: string, size: Size): void {
  setSetting('sizes', { ...getSettings().sizes, [id]: size })
}

/** The game a tree's daily is dealt in: its default size. */
export function dailyGame(id: string): string {
  const sizes = sizesFor(id)
  return gameId(id, sizes ? sizes.default : null)
}

/** How far a size reaches, for the info tiers: undefined for the whole tree. */
export function reach(size: Size | null): number | undefined {
  return typeof size === 'number' ? size : undefined
}

/** "2,000", or "all". */
export function sizeText(size: Size): string {
  return size === 'all' ? 'all' : size.toLocaleString('en')
}

/** "2k", for a slider's marks and a chip. */
export function shortSize(size: Size): string {
  if (size === 'all') return 'All'
  return size >= 1000 && size % 1000 === 0 ? `${size / 1000}k` : String(size)
}

/** The slider's marks: each stop, then the whole tree, at the logarithm of its
 *  size, since 500 to 600 matters and 30,000 to 30,100 does not. The whole
 *  tree's count is not known until it loads, so it sits a doubling past the
 *  last stop. */
export function sliderMarks(sizes: Sizes): { value: number; size: Size; label: string }[] {
  const last = sizes.stops[sizes.stops.length - 1]
  return [
    ...sizes.stops.map((s) => ({ value: Math.log(s), size: s as Size, label: shortSize(s) })),
    { value: Math.log(last * 2), size: 'all', label: shortSize('all') },
  ]
}

// One cut per tree object and size, so the engine's indexes, which key on the
// dataset, are built once a size.
const cuts = new WeakMap<Dataset, Map<number, Dataset>>()

function atSize(ds: Dataset, size: Size | null): Dataset {
  if (size === null || size === 'all') return ds
  let bySize = cuts.get(ds)
  if (!bySize) cuts.set(ds, (bySize = new Map()))
  let out = bySize.get(size)
  if (!out) {
    const tree = cut(ds.tree, size)
    out = tree === ds.tree ? ds : makeDataset(ds.id, ds.manifest, tree)
    bySize.set(size, out)
  }
  return out
}

/** A game's tree: the dataset, cut to the game's size. */
export async function loadGame(game: string): Promise<Dataset> {
  const { id, size } = parseGame(game)
  return atSize(await loadDataset(id), size)
}

/** The game's tree if its dataset has already loaded, without waiting. */
export function loadedGame(game: string): Dataset | undefined {
  const { id, size } = parseGame(game)
  const ds = loadedDataset(id)
  return ds && atSize(ds, size)
}

/** The game on screen. A round provides it; outside one — a test, a stray
 *  popup — it is the chosen tree at its chosen size. */
export const GameContext = createContext<string | null>(null)

export function useGame(): string {
  const provided = useContext(GameContext)
  const { dataset, sizes } = useSettings()
  return provided ?? gameId(dataset, chosenSize(dataset, sizes))
}
