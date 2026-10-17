/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** A dataset under `data/` to bundle instead of the packaged example — see
   *  src/engine/local.ts. Unset for the ordinary app and the website's root;
   *  the website's full/ build sets it. */
  readonly VITE_BUNDLED_DATASET?: string
  /** Where the website's other build lives, relative to this one — see
   *  OTHER_SITE in App.tsx. Set by `build:pages` alone. */
  readonly VITE_OTHER_SITE?: string
}

interface ImportMetaEnv {
  /** The website, for an app build: where the live catalogue and the trees
   *  not bundled into the app are fetched from (https://…/TreeQuiz/). Unset
   *  on the website itself, which fetches from its own folder. */
  readonly VITE_DATA_BASE?: string
}

declare module 'virtual:treequiz-catalogue' {
  const catalogue: import('./engine/catalogue').Catalogue
  export default catalogue
}
