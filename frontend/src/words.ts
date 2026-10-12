/**
 * The words a dataset's manifest supplies, with the fallbacks the app uses when
 * it supplies none. Every place the app would have said "animal" asks here.
 */
import type { Manifest, Source } from './engine/tree'

export function noun(m: Manifest): string {
  return m.noun || 'leaf'
}

export function nounPlural(m: Manifest): string {
  return m.noun_plural || `${noun(m)}s`
}

/** A leaf's name in both numbers, for counting. */
export interface Nouns {
  one: string
  many: string
}

export const LEAVES: Nouns = { one: 'leaf', many: 'leaves' }

export function nounsOf(m: Manifest | undefined): Nouns {
  return m ? { one: noun(m), many: nounPlural(m) } : LEAVES
}

/** "1 animal", "1,615 animals". */
export function count(n: number, nouns: Nouns): string {
  return `${n.toLocaleString()} ${n === 1 ? nouns.one : nouns.many}`
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

/** The source the popup text comes from, for the licence notice under it: the
 *  one `info_source` names. The first source with a licence is the fallback
 *  only, because it is usually the *tree's* source — the languages popups
 *  credited Wikipedia's CC BY-SA text to Glottolog's CC BY that way. */
export function infoSource(m: Manifest): Source | undefined {
  const named = m.info_source?.toLowerCase()
  return (named ? m.sources?.find((s) => s.name.toLowerCase().startsWith(named)) : undefined)
    ?? m.sources?.find((s) => s.licence)
}
