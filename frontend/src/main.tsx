import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, CssBaseline } from '@mui/material'
// Bundled, not fetched from a CDN: the app is meant to work with no network
// beyond the pictures, and a webfont <link> would have made the way it
// looks depend on one. Variable faces, so every weight is one file.
//
// The build emits every subset — Cyrillic, Greek, Vietnamese — which looks
// wasteful in the output listing and is not: each @font-face carries a
// `unicode-range`, so a reader of Latin text downloads the Latin file and
// nothing else. About 85KB for the pair, not the 250KB the listing suggests.
import '@fontsource-variable/fraunces'
import '@fontsource-variable/inter'
import App from './App'
import { theme } from './theme'
import { setSetting } from './settings'
import { readLink } from './shareLink'
import { entryFor } from './engine/datasets'

// A shared link names its tree. Switched to before the first render, so the
// round mounts on the right dataset and is the one to read the link's seed.
const link = readLink(window.location.search)
if (link.dataset && entryFor(link.dataset)) setSetting('dataset', link.dataset)

// Offline support for the website, which is what makes "Add to Home Screen"
// behave like an app; see pwa/sw.js. Never in development, where a cached build
// would hide every edit.
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('sw.js').catch(() => {
      // A bonus, not a requirement: the app works the same without it.
    })
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </StrictMode>,
)
