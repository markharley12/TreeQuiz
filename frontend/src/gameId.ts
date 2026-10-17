/**
 * A game's name: a tree, and for a sized tree the size it is played at —
 * `animals@2000`, `animals@all`; an unsized tree's game is its id.
 * Why the size is part of the name is in sizes.ts. Kept apart from it, with no
 * imports, so a link can be read without loading the registry.
 */
import type { Size } from './settings'

export function gameId(id: string, size: Size | null): string {
  return size === null ? id : `${id}@${size}`
}

/** A game's tree and size; null for an unsized tree. A tree's id is a
 *  directory name, which never holds an `@`. */
export function parseGame(game: string): { id: string; size: Size | null } {
  const at = game.lastIndexOf('@')
  if (at === -1) return { id: game, size: null }
  const raw = game.slice(at + 1)
  return { id: game.slice(0, at), size: raw === 'all' ? 'all' : Number(raw) }
}

export const treeOf = (game: string) => parseGame(game).id
