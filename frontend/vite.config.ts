import { createHash } from 'node:crypto'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import type { Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const here = (path: string) => fileURLToPath(new URL(path, import.meta.url))

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

        // Trees and popup text are cached on first use; see LAZY in sw.js.
        const lazy = (name: string) => /(tree|info)-[^/]*\.json$/.test(name)
        const all = [...built, ...copied].sort()
        if (!all.some(lazy)) throw new Error('No dataset assets in the build: have their names changed?')

        const fills: [string, string][] = [
          ["const VERSION = 'dev'", `const VERSION = '${hash.digest('hex').slice(0, 12)}'`],
          ['const FILES = []', `const FILES = ${JSON.stringify(all.filter((name) => !lazy(name)))}`],
          ['const LAZY = []', `const LAZY = ${JSON.stringify(all.filter(lazy))}`],
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
  plugins: [react(), serviceWorker()],
  // Relative, so one build works wherever it is put: at a domain's root or
  // under GitHub Pages' /TreeQuiz/. An absolute '/' left TaxoQuiz's Pages site
  // blank — every script requested from the domain root.
  base: './',
  server: {
    host: true,
    // Reaching the dev server from a phone over Tailscale; see TaxoQuiz's
    // vite.config.ts for why only `.ts.net` is allowed.
    allowedHosts: ['.ts.net'],
    // The datasets are read from the repo's datasets/, one level above this
    // project, rather than copied into it. Vite serves nothing outside its root
    // by default, so without this the dev server 403s every tree — while the
    // build, which does not apply the rule, works fine.
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
