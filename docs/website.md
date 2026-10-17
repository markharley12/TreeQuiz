# The website: what TaxoQuiz learned publishing one

*From "The website" in TaxoQuiz's CLAUDE.md (Sep–Oct 2026). TreeQuiz's service
worker (`frontend/pwa/sw.js`) and its build plugin (`vite.config.ts`) are
TaxoQuiz's, and their comments carry the rules: a page is always exactly one
build, cache-first, a new worker waits, trees and popup text are cached on
first use. This file keeps what those comments do not: the incidents behind
them, how they were verified, and what the second, bigger site taught. That is
the part phase 4 (download and delete) builds on.*

TaxoQuiz was deployed by a Pages workflow on every push, from
`npm run build:pages`: tests, build, publish `frontend/dist`. Pages is free
for a public repo; TreeQuiz's runs by hand while the repo is private.

It is also the iPhone route. An iPhone cannot install an app from a file the
way Android takes an APK (that needs the App Store or TestFlight, a $99/year
developer account and a Mac); *Add to Home Screen* on the website needs none of
it. Not yet tried on a real iPhone.

## Two builds on one origin (TaxoQuiz Full, Oct 2026)

TaxoQuiz put its 41,000-species build at `/TaxoQuiz/full/` beside the
530-species one at the root, built from a dataset committed for the purpose
(~57MB of history per refresh, which is why TreeQuiz keeps the big tree in a
release instead). Sharing an origin broke three things one build never noticed:

- **Caches belong to the origin, not the scope.** Every worker deleted every
  `taxoquiz-*` cache but its own, so each site wiped the other's on update.
  Caches are named for their scope (`treequiz-<scope>-<version>` here).
- **The root worker's scope contains `full/`.** It answered *every* navigation
  with its own `index.html`, so opening Full served the example. A worker
  answers only its own page; other navigations go to the network.
- **`localStorage` belongs to the domain**, so each site would resume the
  other's round on a secret it does not hold. TreeQuiz keys every round,
  tally and view by tree (`treequiz:<key>:<id>`); only settings are shared.

**The first deploy left `/full/` blank for anyone who had visited before**: 30
seconds of white in the owner's Chrome. The *old* root worker, still in
charge, answered `/full/` with its cached page, whose script 404'd. The tell
was the tab title ("TaxoQuiz", not "TaxoQuiz Full"). TaxoQuiz's fix was a
one-time migration (a worker finding a legacy cache takes over and reloads the
pages in scope); TreeQuiz's worker drops it, having no legacy caches. Two
details worth keeping if a migration is ever needed again: **start the reload,
do not await it** (awaiting inside `activate` deadlocked every tab, since a
navigation is held until activation finishes), and **hash the worker into its
own version**, or a change to the worker alone keeps the old cache name.

## Big text is lazy

Full's 45.6MB of popup text was cached on first use, not precached, or every
phone that opened the site for one round would have downloaded it. TreeQuiz
does the same for every tree and every popup file (`LAZY`). Measured on
TaxoQuiz Full: tree 7.5MB → 1.2MB gzipped, text 45.6MB → 9.8MB. An Android app
showing ~47MB of storage is most likely the WebView's cache of the
uncompressed text after one popup; not confirmed on a device.

The size slider changes this again: text is split into tiers by size
(`docs/scaling.md`), so a round at the default fetches about a sixth of it.

## Decisions that are easy to get quietly wrong

- **`base: './'`.** One build then works under Pages' `/TreeQuiz/`, at a
  domain root, and inside the Android app. With `/` the Pages site is blank.
- **The worker is hand-written** and the plugin writes in `VERSION` (a hash of
  every built file and the worker) and the file lists, throwing if a
  placeholder has gone rather than shipping a worker that caches nothing.
- **Not registered in dev**, where it would hide edits, **nor inside
  Capacitor**, where the files are already on the device and a worker could
  only serve the previous version after an APK update.
- **Other origins are not cached.** Wikimedia's pictures carry their own
  licences and would fill the phone.
- **Every font subset is precached**, about 300KB more than `unicode-range`
  would fetch. Accepted rather than special-cased.
- **The icon is full-bleed paper**, because iOS fills transparency with black
  and a maskable icon may be cropped to a circle; the drawing stays in the
  central 80%. `pwa/render-icons.sh` renders the PNGs with headless Chrome.

## How it was verified, and what was not

On a build served under `/TaxoQuiz/` by a local static server, as Pages
serves it: the worker activated at its scope with every file cached; with the
server killed, a reload came from the cache and a seeded round played. Two
builds on one origin: both workers registered with separate caches, `full/`
loaded Full while the root worker was active, each site's round saved under
its own key. **The in-app browser pane refuses service workers** ("unknown
error fetching the script"), so this needs a real Chrome.

The update flow was checked across two real deploys: the first open after a
deploy served the *old* build whole with the new worker waiting; after the
tab closed, the next visit had the new build and the old cache was gone.

Not verified: a guess made offline (the engine path is covered by the
suites), *Add to Home Screen* on an iPhone, and why Chrome screenshots of the
offline page timed out while the page kept answering scripts.
