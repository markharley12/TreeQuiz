# The Android app: what TaxoQuiz's taught

*From "The Android app" in TaxoQuiz's CLAUDE.md (Sep 2026), for phase 5 of
`taxoquiz-merge-plan.md`, which brings Capacitor back. Nothing here is built
yet: TreeQuiz has no `android/` project. Names below are TaxoQuiz's unless
marked; the plan's choices for TreeQuiz are at the end.*

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
  from install; a bundled tree can be hidden, not deleted.
- CI's APK job back, as TaxoQuiz had it: it caught a broken Android lint that
  nothing else ran.

Not done in either repo: iOS.
