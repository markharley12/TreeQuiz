/**
 * The words a dataset's manifest supplies, with the fallbacks the app uses when
 * it supplies none. Every place the app would have said "animal" asks here.
 */
import type { Manifest } from './engine/tree'

export function noun(m: Manifest): string {
  return m.noun || 'leaf'
}

export function nounPlural(m: Manifest): string {
  return m.noun_plural || `${noun(m)}s`
}

export function shortTitle(m: Manifest): string {
  return m.short_title || m.title
}

/** "a field", "an animal". */
export function withArticle(word: string): string {
  return `${/^[aeiou]/i.test(word) ? 'an' : 'a'} ${word}`
}

/** Bulk guessing opens once the deepest group known to hold the answer is at
 *  least this warm. A manifest can move it; half way is the default, which on
 *  the Linnaean ladder is an order — where TaxoQuiz settled after a player
 *  could not bulk-guess stingrays at family level. */
export function bulkUnlock(m: Manifest): number {
  return typeof m.bulk_unlock === 'number' ? m.bulk_unlock : 0.5
}
