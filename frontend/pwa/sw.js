// The service worker: what lets TreeQuiz open with no connection once it has
// been visited, and so what makes "Add to Home Screen" behave like an app.
// TaxoQuiz's, less the migration it needed when two builds shared an origin.
//
// The build (`serviceWorker()` in vite.config.ts) fills in VERSION and FILES
// and emits this as dist/sw.js. One rule decides everything below: **a
// page is always exactly one build.** Files are named by content hash and a
// deploy replaces all of them, so:
//
// - Everything is served cache-first, index.html included.
// - A new build installs in the background and **waits** — no skipWaiting() —
//   until every page of the old one is closed. Taking over mid-round would
//   swap the code under a page that is still running the old one.
// - The old cache is deleted on activate, when nothing uses it any more.
//
// (One exception, below: a build from before the downloads is replaced at
// once, since its pages break.) So an update reaches a player the second time they open the app after a
// deploy. That is the price of never breaking a round in play.
//
// **The trees are not here.** They are downloads the player chose, kept by the
// page itself in a cache of their own, `treequiz-data`, keyed by URLs that
// carry each file's content hash (src/engine/downloads.ts). This worker never
// touches that cache — its clean-up below deletes only names starting with
// its own PREFIX — so a deploy never deletes a download, and it never answers
// for `data/` or `datasets.json`: the page fetches those itself, and the
// catalogue must come from the network to say what is new.

const VERSION = 'dev'
const FILES = []

const SCOPE = self.registration.scope
const PREFIX = `treequiz-${new URL(SCOPE).pathname}-`
const CACHE = PREFIX + VERSION

const url = (name) => new URL(name, SCOPE).href
const PRECACHED = new Set(FILES.map(url))

// The one exception to waiting. Builds before the downloads kept the trees in
// the build itself, fetched from `assets/tree-<hash>.json` on first open, so
// once a deploy removed those files an old page could open no tree it had not
// opened before: "Could not load …/assets/tree-CU7Kz8S9.json" on every tree
// but the last played, seen on the live site the day the downloads went up,
// and lasting until every TreeQuiz tab was closed. So a worker that finds such
// a build's cache takes over at once and reloads its pages; a round in play is
// saved, and resumes. Every cache of this layout carries LAYOUT, which is how
// an old one is told apart: their contents cannot be, since an old build
// cached its trees only once opened. The first deploy after this one also
// takes over once from the build before it, which had no LAYOUT entry yet.
const LAYOUT = url('__layout-downloads')
const replacingOld = async () => {
  for (const key of await caches.keys()) {
    if (!key.startsWith(PREFIX) || key === CACHE) continue
    if (!(await (await caches.open(key)).match(LAYOUT))) return true
  }
  return false
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => Promise.all([cache.addAll(FILES), cache.put(LAYOUT, new Response('1'))]))
      .then(replacingOld)
      .then((old) => old && self.skipWaiting()),
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    replacingOld().then(async (old) => {
      const keys = await caches.keys()
      await Promise.all(keys.filter((key) => key.startsWith(PREFIX) && key !== CACHE).map((key) => caches.delete(key)))
      if (!old) return
      await self.clients.claim()
      // Started and NOT awaited: a navigation's request is held until this
      // worker has activated, so awaiting it here deadlocks — TaxoQuiz's
      // worker froze every tab on the origin that way.
      for (const client of await self.clients.matchAll({ type: 'window' })) {
        client.navigate(client.url).catch(() => {})
      }
    }),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return
  const target = new URL(request.url)
  target.search = ''
  const href = target.href

  // The page itself, under either name it is reached by — and only those, so
  // a link's ?d=…&seed=… still opens the cached page.
  if (request.mode === 'navigate') {
    if (href !== SCOPE && href !== url('index.html')) return
    event.respondWith(caches.open(CACHE).then((cache) => cache.match('index.html')).then((hit) => hit ?? fetch(request)))
    return
  }

  // `ignoreVary`: a module script's request carries an Origin header that the
  // install's requests did not, so a server answering `Vary: Origin` (Vite's
  // preview does; GitHub Pages does not) made every module a miss — and the
  // miss, after a deploy, fetched a file the server no longer had. The files
  // are named by content, so no header can make a cached one wrong.
  if (PRECACHED.has(href)) {
    event.respondWith(caches.open(CACHE).then((cache) => cache.match(request, { ignoreVary: true })).then((hit) => hit ?? fetch(request)))
  }
  // Anything else goes to the network untouched: the trees and the catalogue
  // (see above), and other origins, such as the Wikimedia pictures, which carry
  // their own licences and would fill the phone.
})
