import { createHash } from 'node:crypto'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import { loadEnv, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import { ASK_BYTES, downloadSet, sizeOf, type Catalogue, type CatalogueTree } from './src/engine/catalogue.ts'
import { leaves } from './src/engine/tree.ts'

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url))
const sha = (data: string | Buffer) => createHash('sha256').update(data).digest('hex')

const CATALOGUE_ID = 'virtual:treequiz-catalogue'

/**
 * Every tree under the repo's `datasets/`, and the files to serve for each.
 *
 * Every `*.json` beside a manifest is one of the tree's files — `tree.json`,
 * `info.json`, `info-<n>.json` — so a new kind of file needs nothing here. In a
 * build each is named by its content (`data/maths/tree-3f2a….json`), which is
 * what lets a download be kept by URL for good; the dev server serves them
 * under their own names. A manifest with no `tree.json` beside it is a remote
 * tree, whose files the Pages workflow fetches from a release: without them
 * the build still works, and lists the tree with no files.
 *
 * An app build (`dataBase` set, see VITE_DATA_BASE) bundles the trees small
 * enough to download without asking and leaves the rest to the website.
 */
function scanDatasets(build: boolean, dataBase: string | undefined, test: boolean) {
  const trees: CatalogueTree[] = []
  const emit = new Map<string, Buffer>()
  // The tests play on trees of their own too: tests/fixtures/ holds TaxoQuiz's
  // curated 530 animals, small and fixed, which no build ships.
  const ids = (root: string) => readdirSync(root).sort().map((id) => ({ root, id }))
  const found = [...ids(here('../datasets')), ...(test ? ids(here('../tests/fixtures')) : [])]
  for (const { root, id } of found) {
    const manifestPath = `${root}/${id}/manifest.json`
    if (!existsSync(manifestPath)) continue
    const manifestText = readFileSync(manifestPath, 'utf8')
    const manifest = JSON.parse(manifestText)
    const names = readdirSync(`${root}/${id}`).filter((n) => n.endsWith('.json') && n !== 'manifest.json').sort()
    if (!names.includes('tree.json')) {
      trees.push({ id, manifest, version: null, files: null })
      continue
    }
    const files: CatalogueTree['files'] = {}
    const sources = new Map<string, Buffer>()
    const version = createHash('sha256').update(manifestText)
    for (const name of names) {
      const source = readFileSync(`${root}/${id}/${name}`)
      const hash = sha(source).slice(0, 12)
      version.update(name).update(hash)
      const url = build ? `data/${id}/${name.replace(/\.json$/, '')}-${hash}.json` : `data/${id}/${name}`
      files[name] = { url, bytes: source.length, gzip: gzipSync(source).length }
      sources.set(url, source)
    }
    const tree = JSON.parse(sources.get(files['tree.json'].url)!.toString('utf8'))
    const entry: CatalogueTree = { id, manifest, version: version.digest('hex').slice(0, 12), files, leaves: leaves(tree).length }
    if (dataBase) {
      // The app: small trees ride inside it, big ones come from the website.
      if (sizeOf(entry, downloadSet(entry)).bytes > ASK_BYTES) {
        trees.push({ ...entry, files: null })
        continue
      }
      entry.bundled = true
    }
    trees.push(entry)
    for (const [url, source] of sources) emit.set(url, source)
  }
  return { catalogue: { trees } satisfies Catalogue, emit }
}

/** The catalogue as a module (`virtual:treequiz-catalogue`), the dev server's
 *  `data/` and `datasets.json`, and in a build those files emitted. See
 *  src/engine/catalogue.ts for what the catalogue is for. */
function catalogue(): Plugin {
  let scanned: ReturnType<typeof scanDatasets> | undefined
  let build = false
  let dataBase: string | undefined
  let test = false
  const scan = () => (scanned ??= scanDatasets(build, dataBase, test))
  return {
    name: 'treequiz-catalogue',
    configResolved(config) {
      build = config.command === 'build'
      test = config.mode === 'test'
      dataBase = loadEnv(config.mode, config.envDir || process.cwd(), 'VITE_').VITE_DATA_BASE || undefined
    },
    resolveId(id) {
      if (id === CATALOGUE_ID) return '\0' + CATALOGUE_ID
    },
    load(id) {
      if (id === '\0' + CATALOGUE_ID) return `export default ${JSON.stringify(scan().catalogue)}`
    },
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url ?? '').split('?')[0]
        const body = path === '/datasets.json'
          ? Buffer.from(JSON.stringify(scan().catalogue))
          : scan().emit.get(path.slice(1))
        if (!body) return next()
        res.setHeader('Content-Type', 'application/json')
        res.end(body)
      })
    },
    generateBundle() {
      const { catalogue, emit } = scan()
      for (const [fileName, source] of emit) this.emitFile({ type: 'asset', fileName, source })
      this.emitFile({ type: 'asset', fileName: 'datasets.json', source: JSON.stringify(catalogue) })
    },
  }
}

/** Emit dist/sw.js and dist/manifest.webmanifest: pwa/sw.js with this build's
 *  file lists and a version hash written in. See sw.js for how it caches and
 *  why it waits. */
function serviceWorker(): Plugin {
  return {
    name: 'treequiz-service-worker',
    apply: 'build',
    generateBundle: {
      // After Vite has emitted index.html, so it is in the bundle to be listed.
      order: 'post',
      handler(_, bundle) {
        this.emitFile({ type: 'asset', fileName: 'manifest.webmanifest', source: readFileSync(here('pwa/manifest.webmanifest'), 'utf8') })

        const built = Object.keys(bundle).filter((name) => !name.endsWith('.map')).sort()
        const copied = readdirSync(here('public')).sort()
        const hash = createHash('sha256')
        for (const name of built) {
          const out = bundle[name]
          hash.update(name).update(out.type === 'asset' ? out.source : out.code)
        }
        for (const name of copied) hash.update(name).update(readFileSync(here(`public/${name}`)))
        // The worker too, or a change to it alone would keep the old version name.
        let source = readFileSync(here('pwa/sw.js'), 'utf8')
        hash.update(source)

        // The trees are not the build's to keep: they are downloads, held in
        // their own cache so a deploy never deletes them (engine/downloads.ts).
        // The catalogue is always asked of the network, being how a page learns
        // of newer trees.
        const data = (name: string) => name.startsWith('data/') || name === 'datasets.json'
        const all = [...built, ...copied].sort()
        if (!all.includes('datasets.json')) throw new Error('No catalogue in the build: has catalogue() gone?')

        const fills: [string, string][] = [
          ["const VERSION = 'dev'", `const VERSION = '${hash.digest('hex').slice(0, 12)}'`],
          ['const FILES = []', `const FILES = ${JSON.stringify(all.filter((name) => !data(name)))}`],
        ]
        for (const [from, to] of fills) {
          // Loud rather than quietly shipping a worker that caches nothing.
          if (!source.includes(from)) throw new Error(`pwa/sw.js no longer contains: ${from}`)
          source = source.replace(from, to)
        }
        this.emitFile({ type: 'asset', fileName: 'sw.js', source })
      },
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), catalogue(), serviceWorker()],
  // Relative, so one build works wherever it is put: at a domain's root or
  // under GitHub Pages' /TreeQuiz/. An absolute '/' left TaxoQuiz's Pages site
  // blank — every script requested from the domain root.
  base: './',
  server: {
    host: true,
    // Reaching the dev server from a phone over Tailscale; see TaxoQuiz's
    // vite.config.ts for why only `.ts.net` is allowed.
    allowedHosts: ['.ts.net'],
    // The tests read the repo's datasets/, one level above this project, by
    // glob, and Vite serves nothing outside its root by default. (The app's
    // own trees come through catalogue()'s middleware, which is not bound by it.)
    fs: { allow: ['..'] },
  },
  build: {
    // The warning fires on the uncompressed bundle; React 19, MUI and
    // react-d3-tree are ~600 kB minified and ~186 kB gzipped, measured in
    // TaxoQuiz. Re-measure before raising it.
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: 'jsdom',
    restoreMocks: true,
    // .tsx too: without it App.test.tsx is silently not run.
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
