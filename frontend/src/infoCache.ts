// One client-side cache of popup info, shared by everything that shows any.
//
// The same lookup has three callers — the popup, the hover preview and the
// thumbnail on the node box — and without it hovering a node you had already
// opened would look it up again. It also makes the thumbnails possible at all:
// a node can only show a picture if something already knows its URL. What is
// expensive is the pictures, fetched once an <img> points at one, not the JSON.
import { useSyncExternalStore } from 'react'
import { fetchInfo, type Info } from './api'

// Keyed on dataset *and* name, which is load-bearing rather than tidy: in
// TaxoQuiz 1,047 names appeared in two datasets with different text, and keyed
// on name alone, switching dataset quietly served the other one's article.
//
// `null` means "asked, and the tree has no such node", cached as firmly as a
// hit. `undefined` from `cachedInfo` means nobody has asked yet.
const cache = new Map<string, Info | null>()
const inflight = new Map<string, Promise<Info | null>>()
const listeners = new Set<() => void>()
let version = 0

// A dataset id cannot contain a newline (it is a directory name), so this
// cannot collide the way `dataset + name` would.
const keyFor = (name: string, dataset: string) => `${dataset}\n${name}`

export function cachedInfo(name: string, dataset: string): Info | null | undefined {
  return cache.get(keyFor(name, dataset))
}

export function loadInfo(name: string, dataset: string): Promise<Info | null> {
  const key = keyFor(name, dataset)
  const known = cache.get(key)
  if (known !== undefined || cache.has(key)) return Promise.resolve(known ?? null)

  const pending = inflight.get(key)
  if (pending) return pending

  const request = fetchInfo(dataset, name).then(
    (info) => {
      cache.set(key, info)
      inflight.delete(key)
      version++
      for (const listener of listeners) listener()
      return info
    },
    () => {
      // A transient failure is deliberately not cached, so the next hover
      // retries rather than the node being permanently blank.
      inflight.delete(key)
      return null
    },
  )
  inflight.set(key, request)
  return request
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

const snapshot = () => version

/** Re-render when anything lands in the cache. */
export function useInfoCache(): number {
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}
