/**
 * The catalogue: every tree there is, with what downloading it costs.
 *
 * The build writes it twice (`catalogue()` in vite.config.ts): into the bundle
 * as `virtual:treequiz-catalogue`, so the front page can list every tree with
 * no network, and beside the site as `datasets.json`, which a running app
 * fetches to learn of newer versions — a page kept open over a deploy, or the
 * Android app, whose trees come from the website.
 *
 * Plain data and pure functions only: vite.config.ts imports this file too.
 */
// With its extension, as Vite's native config loader will want of every
// import vite.config.ts makes.
import type { Manifest } from './tree.ts'

export interface CatalogueFile {
  /** Relative to the catalogue it came from; carries the file's content hash,
   *  so a URL is never reused for different bytes. */
  url: string
  /** As stored on the device. */
  bytes: number
  /** As sent over the wire: Pages gzips JSON. */
  gzip: number
}

export interface CatalogueTree {
  id: string
  manifest: Manifest
  /** A hash over the manifest and every file. Null when there are no files. */
  version: string | null
  /** Keyed by the file's name in `datasets/<id>/`: `tree.json`, `info.json`,
   *  `info-<n>.json`. Null for a remote tree this build did not have — its
   *  files are on the website, and the live catalogue there says where. */
  files: Record<string, CatalogueFile> | null
  /** Shipped inside the app, so on the device from install and never
   *  downloaded. Only an app build (VITE_DATA_BASE set) bundles anything. */
  bundled?: boolean
}

export interface Catalogue {
  trees: CatalogueTree[]
}

/** Enough of a tree to size it: a catalogue entry, or a copy on the device. */
interface Sized {
  manifest: Manifest
  files: Record<string, { bytes: number; gzip: number }> | null
}

/** Above this many bytes on the device, a tree asks before it downloads.
 *  Every tree today is under 1.3MB; TaxoQuiz Full's tree alone is 7.5MB. */
export const ASK_BYTES = 5_000_000

/** The files a download fetches up front: the tree, and the popup text —
 *  for a tree with sizes, the tiers its default size needs (each tier up to
 *  the first that reaches it, as the slider reads them), since the others are
 *  only wanted once a player raises the slider. The rest are fetched the
 *  first time they are asked for. */
export function downloadSet(entry: Sized): string[] {
  if (!entry.files) return []
  const upTo = (entry.manifest as { sizes?: { default?: number } }).sizes?.default ?? Infinity
  const names = Object.keys(entry.files)
  const tiers = names.map((name) => Number(name.match(/^info-(\d+)\.json$/)?.[1])).filter((n) => !Number.isNaN(n))
  const reaches = Math.min(...tiers.filter((n) => n >= upTo))
  return names.filter((name) => {
    if (name === 'tree.json' || name === 'info.json') return true
    const n = Number(name.match(/^info-(\d+)\.json$/)?.[1])
    return n < upTo || n === reaches
  }).sort()
}

/** Bytes on the device, and over the wire, of a set of a tree's files. */
export function sizeOf(entry: Pick<Sized, 'files'>, names: string[]): { bytes: number; gzip: number } {
  let bytes = 0, gzip = 0
  for (const name of names) {
    const f = entry.files?.[name]
    if (f) { bytes += f.bytes; gzip += f.gzip }
  }
  return { bytes, gzip }
}

/** "1.3 MB", "820 KB": decimal units, as phones' storage settings count. */
export function formatBytes(n: number): string {
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 0 : 1)} MB`
  return `${Math.max(1, Math.round(n / 1e3))} KB`
}
