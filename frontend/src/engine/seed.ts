/**
 * Shareable game seeds. Port of `treequiz/seed.py`, which explains the format
 * and why a seed fingerprints its dataset.
 *
 * This is the module where a near miss costs most: a seed must name the same
 * leaf in both engines, so the hashing is byte-for-byte Python's, including
 * treating the whole 256-bit digest as one integer, which is what `BigInt` is
 * for.
 */
import { sha256 } from './sha256'
import { labelOf, type RawNode } from './tree'

export const ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
export const FINGERPRINT_LEN = 4
export const BODY_LEN = 6

const utf8 = new TextEncoder()

function digestInt(text: string): bigint {
  let n = 0n
  for (const byte of sha256(utf8.encode(text))) n = (n << 8n) | BigInt(byte)
  return n
}

function encode(n: bigint, length: number): string {
  const base = BigInt(ALPHABET.length)
  const out: string[] = []
  for (let i = 0; i < length; i++) {
    out.push(ALPHABET[Number(n % base)])
    n /= base
  }
  return out.reverse().join('')
}

export function fingerprint(leaves: RawNode[]): string {
  return encode(digestInt(leaves.map((s) => `${labelOf(s)}\n`).join('')), FINGERPRINT_LEN)
}

/** The tag a seed carries, however it was typed, or null for something that
 *  is not a seed — for finding which dataset a pasted seed belongs to. */
export function tagOf(seed: string): string | null {
  try {
    return normalise(seed).slice(0, FINGERPRINT_LEN)
  } catch {
    return null
  }
}

/** `isoDay` is `YYYY-MM-DD`. */
export function bodyForDate(isoDay: string): string {
  return encode(digestInt(`treequiz-daily:${isoDay}`), BODY_LEN)
}

/** Today in UTC — the same date `App.tsx` stamps a saved session with, so a
 *  daily round and the check that expires it agree on when the day ends. */
export function utcToday(): string {
  return new Date().toISOString().slice(0, 10)
}

export function newBody(): string {
  // 256 is a multiple of 32, so a byte modulo the alphabet is unbiased.
  const bytes = crypto.getRandomValues(new Uint8Array(BODY_LEN))
  return Array.from(bytes, (b) => ALPHABET[b % ALPHABET.length]).join('')
}

export function makeSeed(leaves: RawNode[], opts: { body?: string; day?: string } = {}): string {
  const body = opts.day !== undefined ? bodyForDate(opts.day) : opts.body
  return `${fingerprint(leaves)}-${body || newBody()}`
}

/** Accept what a person actually types: any case, spaces, missing dash. */
export function normalise(seed: string): string {
  const cleaned = [...seed.toUpperCase()].filter((c) => ALPHABET.includes(c)).join('')
  if (cleaned.length !== FINGERPRINT_LEN + BODY_LEN) {
    throw new Error(
      `'${seed}' is not a seed — expected ${FINGERPRINT_LEN + BODY_LEN} characters like ABCD-234567.`,
    )
  }
  return `${cleaned.slice(0, FINGERPRINT_LEN)}-${cleaned.slice(FINGERPRINT_LEN)}`
}

/** A seed's body, once its tag is checked against the tree. Throws for a seed
 *  made on another tree. */
export function bodyOf(seed: string, leaves: RawNode[]): string {
  seed = normalise(seed)
  const [fp, body] = seed.split('-')
  const expected = fingerprint(leaves)
  if (fp !== expected) {
    throw new Error(`Seed '${seed}' is for a different dataset (its tag is ${fp}, this one is ${expected}).`)
  }
  return body
}

/** A number in 0..n-1 from a hash of `key`: the one source of chance a seed
 *  may use, since both engines must draw the same. */
export function draw(key: string, n: number): number {
  return Number(digestInt(key) % BigInt(n))
}

export function resolve(seed: string, leaves: RawNode[]): RawNode {
  return leaves[draw(`treequiz-seed:${bodyOf(seed, leaves)}`, leaves.length)]
}
