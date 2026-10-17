import type { CapacitorConfig } from '@capacitor/cli'

// Capacitor wraps the app build (`npm run build:app`, into `dist/`) in a native
// Android shell, served from inside the APK at https://localhost. Every tree is
// bundled into it, animals included, so it plays offline from install. See
// docs/android.md.
//
// `appId` is the package name, and permanent after the first store upload,
// since a store treats a different ID as a different app. TaxoQuiz's was
// `io.github.markharley12.taxoquiz`: a different app, already on phones.
const config: CapacitorConfig = {
  appId: 'io.github.markharley12.treequiz',
  appName: 'TreeQuiz',
  webDir: 'dist',
}

export default config
