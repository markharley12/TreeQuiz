# The Android app: what TaxoQuiz's taught

*From "The Android app" in TaxoQuiz's CLAUDE.md (Sep 2026), for phase 5 of
`taxoquiz-merge-plan.md`. Names below are TaxoQuiz's unless marked; what
TreeQuiz built is in the first section.*

## TreeQuiz's app (17 Oct 2026)

`npm run android:apk` (in `frontend/`) builds the web app in **app mode**
(`vite build --mode app`, reading `.env.app`: `VITE_DATA_BASE` is the Pages
site), syncs it into `android/`, and assembles a debug APK at
`android/app/build/outputs/apk/debug/app-debug.apk`; `android:release` the
same, release, signed when a key is configured. Built here with JDK 21
(`JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64`; the default JDK 25 was not
tried) and `ANDROID_HOME=~/Android/Sdk`; CI's `android` job builds the same
and keeps the APK as an artifact.

- **ID `io.github.markharley12.treequiz`, name TreeQuiz**, one flavour.
  Capacitor pinned to TaxoQuiz's versions (core/android/cli 8.5.2, app
  8.1.1), the newer 8.5.3 being ten days old when added.
- **What is inside: every tree**, animals' 45MB included (14.5MB release
  APK, as TaxoQuiz's Full app was 15MB), so the app plays all of them
  offline from install and never downloads one. An app build without
  animals' files fails rather than shipping without it: on a clean clone,
  fetch the release first (`gh release download <tag> --dir
  datasets/animals`, the tag in its manifest), as CI's APK job does.
  The first APK left animals to the website (6.5MB); the owner wanted it in.
  That build also found that a live catalogue entry of another kind (sized
  where the build's is not, or the reverse) must be ignored (`sameKind` in
  `downloads.ts`): against a site still serving the 530 as `animals`, the
  app took them for its Animals.
- **No Manage trees in the app**: with every tree built in there is nothing
  to download or delete (`ALL_BUNDLED` in `downloads.ts` hides the link), and
  each card says "In the app" with what the tree takes on the phone: all its
  files, compressed, since Android keeps an APK's assets deflated and never
  unpacks them (Animals 9.7 MB, 45.6 MB as text; the owner asked why a
  "46 MB" tree fit a 14.5MB app).
- **No service worker in the app** (`main.tsx`): it is served from its own
  package, so offline already.
- **The back button** (`backButton.ts`, TaxoQuiz's): closes the newest
  popup, dialog or menu; with none open, a game goes Home (which keeps its
  round — TaxoQuiz's way home cleared it, so it minimised instead); on the
  front page it minimises. Hooked: the info popup, stats, Manage trees and
  its delete confirmation, settings, explore's expand-all warning, and the
  round's three confirmations.
- **Icons and splash** are TaxoQuiz's generated resources, copied: the icon
  is the same drawing (`pwa/icon.svg`, identical art).
- **Release signing uses TaxoQuiz's key** (the owner's choice):
  `build.gradle` reads `TREEQUIZ_RELEASE_*` (store file, store password, key
  alias, key password) from `~/.gradle/gradle.properties` or the
  environment, each falling back to its `TAXOQUIZ_RELEASE_*` twin, so the
  passwords stay in one place. Without either a release build is unsigned.
  `npm run android:release` gives `android/app/build/outputs/apk/release/
  app-release.apk`, 4.8MB; checked with `apksigner verify --print-certs`:
  v2 scheme, `CN=TaxoQuiz, O=markharley12`, SHA-256 `85:62:B9:72:…:30:FC:1B:C2`.
  The ID differs, so it neither updates nor replaces TaxoQuiz on a phone.
- **Tested on a real phone** (18 Oct 2026): the owner sideloaded the
  release APK (14.5MB, every tree built in) and it worked throughout.

Capacitor 8 wrapped `frontend/dist` in a native shell (`capacitor.config.ts`,
the Gradle project in `frontend/android/`). The web app is served from inside
the APK, so it rests on the TypeScript engine and needs no server. Built with
`npm run android:apk`. A debug APK (~4.9MB) was sideloaded onto a real phone
and reported working; that is the extent of device testing, not instrumented.

## Easy to get wrong

- **`appId` is permanent after the first store upload**: a store treats a new
  ID as a new app. TaxoQuiz's was `io.github.markharley12.taxoquiz`.
- **`android/` is committed; its copy of the web app is not.**
  `app/src/main/assets/public`, the generated `capacitor.config.json` and
  `local.properties` are in `android/.gitignore`. So a fresh clone has no web
  assets in the Android project until `cap sync`, and a bare `./gradlew` after
  a frontend change packages the *previous* build. `android:apk` builds,
  syncs and assembles in one, so the order cannot be skipped.
- **`sdkmanager` is gone; the `android` CLI replaced it** (cmdline-tools 23,
  Sep 2026). It shows the SDK terms on first run and **collects usage metrics
  by default**: pass `--no-metrics`. Installed: `platform-tools`,
  `platforms;android-36`, `build-tools;35.0.0` (what AGP 8.13 asks for), JDK 21.
- **The emulator was not usable on the dev machine.** Creating a device (a
  ~1.5GB system image) was killed for low memory; a Gradle daemon left behind
  held 1.3GB, so `./gradlew --stop` after building. Test on a phone, which is
  the better test anyway.
- **`npm audit`'s moderate `uuid` advisory** applies only when a caller passes
  a `buf`; it reaches the app through `react-d3-tree`, which calls a bare
  `uuidv4()`, and the build through `@capacitor/cli`'s Xcode tooling. Left
  alone deliberately.

## The back button

With no listener, Capacitor closed the app from any screen, since the app
keeps no browser history. TaxoQuiz's `backButton.ts` (`useCloseOnBack(open,
close)`) keeps a stack of open overlays (the popup, confirmations, explore's
expand-all warning, settings): one press closes the newest, and with none open
`App.minimizeApp()` leaves the round where it was. Native only; in a browser,
back belongs to the browser. **Every new dialog must call the hook**, or back
skips past it and minimises the app underneath. TreeQuiz has more overlays than
TaxoQuiz had (odd one out's and line-up's reveals, the stats dialog), so the
port has more call sites to find.

## Signing

`npm run android:release` signed with a key kept outside the repo:
`~/.android/taxoquiz-release.jks`, its password in `~/.gradle/gradle.properties`
as `TAXOQUIZ_RELEASE_*` (also read from the environment). `build.gradle` signs
release builds only when those are present, so a clone without them builds
unsigned. Certificate SHA-256 `85:62:B9:72:…:30:FC:1B:C2`, valid until 2054.
**Back up the key and its password together**: losing them means no update
can ever be published as that app. It is deliberately not in GitHub secrets
(the owner keeps it on one machine), so CI's APK is a debug build on a fresh
key each run, and a newer CI APK will not install over an older one.
Release and debug APKs have different signatures, so moving a phone from one
to the other needs an uninstall, which loses the saved round.

## Icons

The launcher icon and splash came from `@capacitor/assets`, from
`frontend/assets/logo.png`, which `pwa/render-icons.sh` renders from the same
`pwa/icon.svg` as the website's icons. The tool also reformats
`AndroidManifest.xml` without changing its meaning; revert that after
generating so the diff shows only what changed.

## The Full app, and why TreeQuiz has none

TaxoQuiz built a second app, `io.github.markharley12.taxoquiz.full`, from a
Gradle flavour that differed only in ID and name; what went inside was
whatever `cap sync` last copied, and `@bundle/*` Vite aliases pointed the
build at a dataset (a missing one failed the build, rather than quietly
bundling the example into an app called "Full"). 15MB, carrying a 7.1MB tree
and 43.5MB of text. Flavours moved the APK paths
(`apk/standard/debug/app-standard-debug.apk`, …).

TreeQuiz needs one flavour: the plan's download screen replaces the second
app, and the big tree comes from the Pages site.

## TreeQuiz's choices (from the plan)

- A new app ID, `io.github.markharley12.treequiz`, since TaxoQuiz's is a
  different app already on phones.
- Release signing with a new key or TaxoQuiz's: the owner's call. Reusing it
  does not let TreeQuiz update TaxoQuiz's installs (the ID differs either way).
- The small trees bundled (all nine are ~1.5MB gzipped), so it works offline
  (done, and animals too: see the first section)
  from install; a bundled tree can be hidden, not deleted.
- CI's APK job back, as TaxoQuiz had it: it caught a broken Android lint that
  nothing else ran.

Not done in either repo: iOS.
