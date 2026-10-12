/**
 * A round shared as a link: `…/?d=maths&seed=J3XF-ABC234` opens straight into
 * that round on that tree. A bare seed has to be copied, the site found and
 * the code pasted; a link is one tap. The seed box stays, for a seed read aloud.
 *
 * The dataset rides in the link as well as in the seed. A seed's first four
 * characters fingerprint its tree (see engine/seed.ts), so the seed alone would
 * do — `datasetForSeed` in api.ts is what a pasted seed falls back on — but
 * finding a fingerprint means loading every tree, and a link should open
 * without that.
 */

/** What a link to a round starts with: the page itself, so a dev server or a
 *  copy hosted elsewhere links to itself. */
export function shareBase(page: string): string {
  const url = new URL(page)
  url.search = ''
  url.hash = ''
  url.pathname = url.pathname.replace(/index\.html$/, '')
  return url.href
}

/** A link to a round, or with `odd`, to an odd-one-out set — which a seed
 *  names just as well, so the parameter is what says which game. */
export function shareLink(base: string, dataset: string, seed: string, game: 'round' | 'odd' = 'round'): string {
  const url = new URL(base)
  url.searchParams.set('d', dataset)
  url.searchParams.set(game === 'odd' ? 'odd' : 'seed', seed)
  return url.href
}

export interface Link {
  dataset: string | null
  seed: string | null
  /** An odd-one-out set's seed. */
  odd: string | null
}

/** What a link carries. Validity is the engine's business. */
export function readLink(search: string): Link {
  const params = new URLSearchParams(search)
  const clean = (v: string | null) => (v?.trim() ? v.trim() : null)
  return { dataset: clean(params.get('d')), seed: clean(params.get('seed')), odd: clean(params.get('odd')) }
}

/** The address with a link's parameters taken out, so a reload resumes the
 *  round rather than offering to restart it. */
export function withoutLink(href: string): string {
  const url = new URL(href)
  url.searchParams.delete('d')
  url.searchParams.delete('seed')
  url.searchParams.delete('odd')
  return url.href
}
