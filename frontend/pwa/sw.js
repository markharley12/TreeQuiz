// The service worker: what lets TreeQuiz open with no connection once it has
// been visited, and so what makes "Add to Home Screen" behave like an app.
// TaxoQuiz's, less the migration it needed when two builds shared an origin.
//
// The build (`serviceWorker()` in vite.config.ts) fills in VERSION, FILES and
// LAZY and emits this as dist/sw.js. One rule decides everything below: **a
// page is always exactly one build.** Files are named by content hash and a
// deploy replaces all of them, so:
//
// - Everything is served cache-first, index.html included.
// - A new build installs in the background and **waits** — no skipWaiting() —
//   until every page of the old one is closed. Taking over mid-round would
//   delete the cache under a page whose next lazy load would then 404.
// - The old cache is deleted on activate, when nothing uses it any more.
//
// So an update reaches a player the second time they open the app after a
// deploy. That is the price of never breaking a round in play.

const VERSION = 'dev'
const FILES = []
// Cached the first time they are asked for rather than on install: every
// tree but the one being played, and all the popup text. Precaching those
// would make a phone that came to play one round of maths download the lot.
const LAZY = []

const SCOPE = self.registration.scope
const PREFIX = `treequiz-${new URL(SCOPE).pathname}-`
const CACHE = PREFIX + VERSION

const url = (name) => new URL(name, SCOPE).href
const PRECACHED = new Set(FILES.map(url))
const LAZILY = new Set(LAZY.map(url))

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FILES)))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(
      keys.filter((key) => key.startsWith(PREFIX) && key !== CACHE).map((key) => caches.delete(key)),
    )),
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

  if (PRECACHED.has(href)) {
    event.respondWith(caches.open(CACHE).then((cache) => cache.match(request)).then((hit) => hit ?? fetch(request)))
  } else if (LAZILY.has(href)) {
    event.respondWith(
      caches.open(CACHE).then(async (cache) => {
        const hit = await cache.match(request)
        if (hit) return hit
        const res = await fetch(request)
        // A failure is not kept, so a later attempt with signal tries again.
        if (res.ok) await cache.put(request, res.clone())
        return res
      }),
    )
  }
  // Anything else — other origins, such as the Wikimedia pictures, which carry
  // their own licences and would fill the phone — goes to the network untouched.
})
