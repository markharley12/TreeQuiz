import { lazy, Suspense, useState, useEffect } from 'react'
import {
  Box, Typography, Chip, Stack, CircularProgress, Button, TextField, Tooltip, Alert,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions, IconButton, Link,
} from '@mui/material'
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined'
import { useNarrow } from './media'
import GuessInput from './components/GuessInput'
import GuessList from './components/GuessList'
import SettingsMenu from './components/SettingsMenu'
import DatasetPicker from './components/DatasetPicker'
import DownloadGate from './components/DownloadGate'
import Progress from './components/DownloadProgress'
import OddOneOut from './components/OddOneOut'
import LineUp from './components/LineUp'
import StatsDialog from './components/StatsDialog'
import SizeSlider from './components/SizeSlider'
import { datasetForSeed, fetchGameState, startRound, type TreeNode } from './api'
import { useSettings, setSetting } from './settings'
import { FONT_DISPLAY, PAGE_PAD, TREE_BLEED } from './theme'
import { displayName } from './names'
import { bulkScope, closestGuess, describeClosest, hintAvailable, hintCost } from './endgame'
import { entryFor, storageKey } from './engine/datasets'
import { normalise } from './engine/seed'
import type { Manifest } from './engine/tree'
import { readLink, shareBase, shareLink, withoutLink } from './shareLink'
import { useSharer } from './sharer'
import { guessWarmths, readDailies, recordDaily, shareText } from './results'
import { bulkUnlock, noun, nounPlural, shortTitle } from './words'
import { chooseSize, chosenSize, GameContext, gameId, leafCount, parseGame, shortSize, sizesFor, sizeText, type Size } from './sizes'
import { useDownloads, useTree } from './useDownloads'
import { download } from './engine/downloads'
import { formatBytes } from './engine/catalogue'

// The two trees are drawn with react-d3-tree and d3, a third of the bundle,
// which the front page and odd one out never need: loaded when first drawn.
const GameTree = lazy(() => import('./components/GameTree'))
const ExploreTree = lazy(() => import('./components/ExploreTree'))
// Opened rarely, and most of its parts are its own.
const ManageTrees = lazy(() => import('./components/ManageTrees'))
const treeFallback = <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}><CircularProgress /></Box>

type Mode = 'daily' | 'practice' | 'explore' | 'odd' | 'lineup'
type RoundMode = Exclude<Mode, 'explore' | 'odd' | 'lineup'>
/** The views a tree can be left in and come back to, beside a round. */
type View = Extract<Mode, 'explore' | 'odd' | 'lineup'>
const isView = (v: string | null): v is View => v === 'explore' || v === 'odd' || v === 'lineup'

interface SavedSession {
  mode: RoundMode
  secret: string
  seed: string
  guesses: string[]
  won: boolean
  /** Gave up and asked for the answer. Persisted, or a reload would hand the
   *  round back with the answer already spent. */
  revealed: boolean
  /** Hints bought, and what they added to the score. Kept apart because a
   *  hint's cost depends on the score when it was taken. */
  hints?: number
  hintPoints?: number
  date: string
}

const today = () => new Date().toISOString().slice(0, 10)

/** Each tree keeps its own round, so switching tree and back loses nothing —
 *  and a sized tree one per size (sizes.ts), since the size is the game. */
const sessionKey = (game: string) => storageKey('session', game)
/** Whether a tree was last left in explore, which a reload should return to.
 *  Kept apart from the round, so exploring never overwrites one. */
const viewKey = (game: string) => storageKey('view', game)

function readSession(dataset: string): SavedSession | null {
  try {
    const raw = localStorage.getItem(sessionKey(dataset))
    if (!raw) return null
    const saved: SavedSession = JSON.parse(raw)
    if (saved.mode === 'daily' && saved.date !== today()) return null
    return saved
  } catch {
    return null
  }
}

function readView(dataset: string): string | null {
  try {
    return localStorage.getItem(viewKey(dataset))
  } catch {
    return null
  }
}

function writeStorage(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // Private browsing, or storage full: the round still plays, it just will
    // not survive a reload.
  }
}

/** The same seed however it was typed; false for anything not a seed. */
function sameSeed(a: string, b: string): boolean {
  try {
    return normalise(a) === normalise(b)
  } catch {
    return false
  }
}

/** A round worth asking about before a link replaces it, and worth offering
 *  to resume: something in it, and not over. */
function inProgress(s: SavedSession | null): s is SavedSession {
  return s !== null && !s.won && !s.revealed && (s.guesses.length > 0 || (s.hints ?? 0) > 0)
}

/** The seed row's buttons on a phone, with less padding than the theme's
 *  18px a side and no 64px minimum: at that size three of them pushed "Give
 *  up" onto a row of its own at 390px. */
const SEED_ROW_BUTTON = { whiteSpace: 'nowrap', minWidth: { xs: 0, sm: 64 }, paddingInline: { xs: '8px', sm: '18px' } } as const

interface Boot {
  saved: SavedSession | null
  mode: Mode | null
  linked: string | null
  ask: boolean
}

/** Where a round starts. A carried seed — from a link, or a seed pasted on
 *  another tree — resumes a round that is already that seed, asks before
 *  replacing one in progress, and otherwise starts fresh with nothing restored,
 *  or the old round's tree request would race the new one's start. */
function readBoot(dataset: string, carried: string | null, landing: boolean, odd: string | null, lineup: string | null): Boot {
  const saved = readSession(dataset)
  if (odd !== null) return { saved, mode: 'odd', linked: null, ask: false }
  if (lineup !== null) return { saved, mode: 'lineup', linked: null, ask: false }
  if (carried !== null) {
    if (saved && sameSeed(saved.seed, carried)) return { saved, mode: saved.mode, linked: null, ask: false }
    if (inProgress(saved)) return { saved, mode: saved.mode, linked: carried, ask: true }
    return { saved: null, mode: null, linked: carried, ask: false }
  }
  if (landing) return { saved, mode: null, linked: null, ask: false }
  const view = readView(dataset)
  if (isView(view)) return { saved, mode: view, linked: null, ask: false }
  return { saved, mode: saved?.mode ?? null, linked: null, ask: false }
}

interface Nav {
  /** Show the front page rather than resuming, after a tree is picked there. */
  landing: boolean
  /** A seed to start on arrival. */
  seed: string | null
  /** An odd-one-out set's seed, from a link. */
  odd?: string | null
  /** A line-up set's seed, from a link. */
  lineup?: string | null
}

export default function App() {
  const { dataset, sizes } = useSettings()
  const size = chosenSize(dataset, sizes)
  const game = gameId(dataset, size)
  // The link's seed goes to the first round only; later switches carry their own.
  const [nav, setNav] = useState<Nav>(() => {
    const link = readLink(window.location.search)
    return { landing: false, seed: link.seed, odd: link.odd, lineup: link.lineup }
  })
  const manifest = entryFor(dataset)?.manifest
  const { ready, trees } = useDownloads()
  const [managing, setManaging] = useState(false)
  // Bumped when the tree's saved round is forgotten, to remount it empty.
  const [forgotten, setForgotten] = useState(0)

  useEffect(() => {
    if (manifest) document.title = `${shortTitle(manifest)} — TreeQuiz`
  }, [manifest])

  function switchTo(id: string, next: Nav, toSize?: Size) {
    setNav(next)
    if (toSize !== undefined) chooseSize(id, toSize)
    setSetting('dataset', id)
  }

  if (!manifest) return <Alert severity="error" sx={{ m: 3 }}>No datasets in this build.</Alert>
  const manage = managing && (
    <Suspense fallback={null}>
      <ManageTrees
        open
        onClose={() => setManaging(false)}
        onForgot={(id) => {
          if (id !== dataset) return
          setNav({ landing: true, seed: null })
          setForgotten((n) => n + 1)
        }}
      />
    </Suspense>
  )
  // A tree that is not here and will not fetch itself — a big one, or one
  // only the website has — gets a page that says so, until it is down. Its
  // round, and a link's seed, wait behind it.
  const tree = trees.get(dataset)
  if (tree && !tree.copy && (!tree.offer || tree.offer.ask)) return (
    <>
      <DownloadGate dataset={dataset} ready={ready} onPick={(id) => switchTo(id, { landing: true, seed: null })} onManage={() => setManaging(true)} />
      {manage}
    </>
  )
  // Keyed on the game — the tree, and a sized tree's size — so a switch mounts
  // a fresh round that reads its own saved state, rather than one round's
  // state leaking into another tree or size; and on forgetting, so a round
  // whose saved state was cleared starts over. Everything below the round
  // that asks the engine anything asks about this game.
  return (
    <GameContext.Provider value={game}>
      <Round key={`${game}#${forgotten}`} dataset={dataset} game={game} size={size} manifest={manifest} nav={nav} onSwitch={switchTo} onManage={() => setManaging(true)} />
      {manage}
    </GameContext.Provider>
  )
}

interface RoundProps {
  /** The tree. */
  dataset: string
  /** The tree at its size, which is what every round, set and record is
   *  kept under; the tree's id alone for an unsized tree. */
  game: string
  size: Size | null
  manifest: Manifest
  nav: Nav
  onSwitch: (id: string, next: Nav, size?: Size) => void
  onManage: () => void
}

function Round({ dataset, game, size, manifest, nav, onSwitch, onManage }: RoundProps) {
  const [boot] = useState(() => readBoot(game, nav.seed, nav.landing, nav.odd ?? null, nav.lineup ?? null))
  const saved = boot.saved
  const [mode, setMode] = useState<Mode | null>(boot.mode)
  // The mode of the round in memory, which the front page can resume.
  const [roundMode, setRoundMode] = useState<RoundMode | null>(saved?.mode ?? null)
  const [secret, setSecret] = useState<string | null>(saved?.secret ?? null)
  const [seed, setSeed] = useState<string>(saved?.seed ?? '')
  const [seedInput, setSeedInput] = useState('')
  const narrow = useNarrow()
  const roundSharer = useSharer()
  const resultSharer = useSharer()
  const canShareSheet = roundSharer.canShareSheet
  // The day a daily is for, so one finished after midnight is kept as the day
  // it was dealt rather than the next.
  const [roundDay, setRoundDay] = useState(saved?.date ?? today())
  const [statsOpen, setStatsOpen] = useState(false)
  const [seedError, setSeedError] = useState<string | null>(null)
  // When a rejected seed belongs to another tree: which, to offer playing it there.
  const [seedElsewhere, setSeedElsewhere] = useState<{ id: string; size: Size | null; seed: string } | null>(null)
  const [pendingLink, setPendingLink] = useState<string | null>(boot.ask ? boot.linked : null)
  // A link's odd-one-out set, dealt the first time odd one out opens and then
  // forgotten: coming back to it later resumes whatever set is in progress.
  const [oddLink, setOddLink] = useState<string | null>(nav.odd ?? null)
  const [lineupLink, setLineupLink] = useState<string | null>(nav.lineup ?? null)
  const [guesses, setGuesses] = useState<string[]>(saved?.guesses ?? [])
  const [treeData, setTreeData] = useState<TreeNode | null>(null)
  const [won, setWon] = useState(saved?.won ?? false)
  const [revealed, setRevealed] = useState(saved?.revealed ?? false)
  const [confirmGiveUp, setConfirmGiveUp] = useState(false)
  const [hints, setHints] = useState(saved?.hints ?? 0)
  const [hintPoints, setHintPoints] = useState(saved?.hintPoints ?? 0)
  const [confirmHint, setConfirmHint] = useState(false)
  // What the tree should bring into view when it changes: the newest guess, or
  // after a hint the ??? node, which is what the hint moved.
  const [hintFocus, setHintFocus] = useState(false)
  const [loading, setLoading] = useState(false)
  const [treeLoaded, setTreeLoaded] = useState(false)
  const leaf = noun(manifest)
  const plural = nounPlural(manifest)

  // On mount: take a link out of the address, so a reload resumes the round
  // rather than offering to restart it, and start a carried round if nothing
  // needs asking first.
  useEffect(() => {
    const link = readLink(window.location.search)
    if (link.seed !== null || link.dataset !== null || link.odd !== null || link.lineup !== null) {
      window.history.replaceState(window.history.state, '', withoutLink(window.location.href))
    }
    if (boot.linked !== null && !boot.ask) void startGame('practice', boot.linked)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Draw a resumed round's tree. A round with only hints has one too.
  const playing = mode === 'daily' || mode === 'practice'
  const needsTree = playing && !treeLoaded && secret !== null && (guesses.length > 0 || hints > 0)
  useEffect(() => {
    if (!needsTree) return
    let cancelled = false
    fetchGameState(game, secret!, guesses, hints)
      .then((state) => { if (!cancelled) setTreeData(state) })
      .catch(() => {})
      .finally(() => { if (!cancelled) setTreeLoaded(true) })
    return () => { cancelled = true }
  }, [needsTree]) // eslint-disable-line react-hooks/exhaustive-deps

  // Persist the round whenever it changes, and which view the tree was left in.
  useEffect(() => {
    if (roundMode && secret) {
      const session: SavedSession = {
        mode: roundMode, secret, seed, guesses, won, revealed, hints, hintPoints, date: today(),
      }
      writeStorage(sessionKey(game), JSON.stringify(session))
    }
  }, [game, roundMode, secret, seed, guesses, won, revealed, hints, hintPoints])
  useEffect(() => {
    writeStorage(viewKey(game), isView(mode) ? mode : null)
  }, [game, mode])

  // Keep a finished daily for the stats — once its tree is in, since the
  // squares are read off it. Only the day's first finish is kept, so the same
  // round reloaded, or replayed, changes nothing.
  const dailyOver = roundMode === 'daily' && (won || revealed) && secret !== null
  useEffect(() => {
    if (!dailyOver || (guesses.length > 0 && treeData === null)) return
    recordDaily(game, roundDay, {
      seed, guesses, warmths: guessWarmths(treeData, guesses), hints, hintPoints, won,
    })
  }, [dailyOver, treeData]) // eslint-disable-line react-hooks/exhaustive-deps

  async function startGame(selected: RoundMode, sharedSeed?: string) {
    setSeedError(null)
    setSeedElsewhere(null)
    setLoading(true)
    try {
      const round = await startRound(game, { daily: selected === 'daily', seed: sharedSeed })
      setMode(selected)
      setRoundMode(selected)
      setGuesses([])
      setTreeData(null)
      setTreeLoaded(true)
      setWon(false)
      setRevealed(false)
      setHints(0)
      setHintPoints(0)
      setSecret(round.secret)
      setSeed(round.seed)
      setRoundDay(today())
    } catch (e) {
      // A rejected seed must leave the current round alone rather than
      // half-start one — and if it belongs to another tree, say which.
      const there = sharedSeed === undefined ? null : await datasetForSeed(sharedSeed)
      const where = there && there !== game ? parseGame(there) : null
      const other = where ? entryFor(where.id) : undefined
      if (where && other) {
        const at = where.size === null ? '' : where.size === 'all' ? ', played whole' : ` at ${sizeText(where.size)}`
        setSeedError(where.id === dataset
          ? `That seed is for ${shortTitle(other.manifest)}${at}, a different size.`
          : `That seed is for ${shortTitle(other.manifest)}${at}, a different tree.`)
        setSeedElsewhere({ id: other.id, size: where.size, seed: sharedSeed!.trim() })
      } else {
        setSeedError(e instanceof Error ? e.message : 'Could not start that round')
      }
    } finally {
      setLoading(false)
    }
  }

  async function guessAll(labels: string[]) {
    const next = [...guesses, ...labels]
    setGuesses(next)
    // This fetch is the tree from now on; the resume fetch must not race it.
    setTreeLoaded(true)
    setHintFocus(false)
    setTreeData(await fetchGameState(game, secret!, next, hints))
    if (secret !== null && labels.includes(secret)) setWon(true)
  }

  // A hint shows one more node of the answer's lineage and costs the score again
  // (at least 10). The count goes to the engine; the points stay here, since
  // only the client knows what the score was when each hint was bought.
  async function takeHint() {
    setConfirmHint(false)
    setHintFocus(true)
    const next = hints + 1
    setHintPoints(hintPoints + hintCost(guesses.length + hintPoints))
    setHints(next)
    setTreeLoaded(true)
    setTreeData(await fetchGameState(game, secret!, guesses, next))
  }

  const roundLink = () => shareLink(shareBase(window.location.href), game, seed)

  // The round as a link, to play; and once it is over, how it went, to show.
  function shareRound() {
    void roundSharer.share({ url: roundLink() })
  }

  function shareResult() {
    void resultSharer.share({ text: shareText({
      title: shortTitle(manifest), daily: roundMode === 'daily', day: roundDay,
      warmths: guessWarmths(treeData, guesses), hints, hintPoints, won, link: roundLink(),
    }) })
  }

  // Back to the front page. The round stays saved, and the front page offers it.
  function goHome() {
    setMode(null)
    setOddLink(null)
    setLineupLink(null)
  }

  function resume() {
    if (roundMode) setMode(roundMode)
  }

  // From the settings menu, mid-round: the round is saved under its own tree,
  // so switching costs nothing and switching back resumes it.
  function selectDataset(id: string) {
    if (id !== dataset) onSwitch(id, { landing: mode === null, seed: null })
  }

  const header = (chip: string, extra?: React.ReactNode) => (
    // One row on a phone: a spacer holds the controls at the far end, and
    // "Change mode" becomes an icon, which is what makes the row fit 412px.
    <Stack direction="row" spacing={{ xs: 0.5, sm: 2 }} sx={{ mb: { xs: 1, sm: 2 }, alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
      <Typography variant="h4" sx={{ fontSize: { xs: '1.5rem', sm: '2rem' } }}>{shortTitle(manifest)}</Typography>
      <Chip label={chip} size="small" variant="outlined" />
      {extra}
      <Box sx={{ flex: 1, minWidth: 0 }} />
      {narrow ? (
        <Tooltip title="Home">
          <IconButton size="small" aria-label="Home" onClick={goHome}><HomeOutlinedIcon /></IconButton>
        </Tooltip>
      ) : (
        <Button size="small" variant="text" sx={{ whiteSpace: 'nowrap' }} onClick={goHome}>Home</Button>
      )}
      <SettingsMenu onSelectDataset={selectDataset} />
    </Stack>
  )

  const resumable = roundMode !== null && secret !== null && !won && !revealed && (guesses.length > 0 || hints > 0)
  // Today's daily: the round in memory if that is it, and otherwise its record,
  // which the stats show — a finished daily is not dealt a second time. On a
  // sized tree every size has its own, so the daily is this game's.
  const sizes = sizesFor(dataset)
  const daily = game
  const dailyInMemory = roundMode === 'daily' && secret !== null
  const doneToday = (dailyInMemory && (won || revealed)) || Boolean(readDailies(daily)[today()])
  const dailyResumable = dailyInMemory && resumable

  function openDaily() {
    if (dailyInMemory) resume()
    else if (doneToday) setStatsOpen(true)
    else void startGame('daily')
  }

  // A chip's word for the size played, on a sized tree.
  const sized = (chip: string) => (size === null ? chip : `${chip} · ${shortSize(size, leafCount(dataset))}`)

  if (loading) return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 10 }}><CircularProgress /></Box>
  )

  if (mode === null) return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2, sm: 3 } }}>
      <Box sx={{ width: '100%', maxWidth: 760 }}>
        <Stack direction="row" spacing={1} sx={{ alignItems: 'center', justifyContent: 'center', mb: 0.5 }}>
          <Typography variant="h2" sx={{ fontSize: { xs: '2.6rem', sm: '3.4rem' } }}>TreeQuiz</Typography>
          <SettingsMenu onSelectDataset={selectDataset} />
        </Stack>
        <Typography sx={{ textAlign: 'center', color: 'text.secondary', mb: 3, fontFamily: FONT_DISPLAY, fontStyle: 'italic', fontSize: '1.1rem' }}>
          Find the secret leaf of a tree. Every guess shows where it branches off
          from the answer — the nearer the branch, the warmer the colour.
        </Typography>

        <DatasetPicker selected={dataset} onPick={(id) => id !== dataset && onSwitch(id, { landing: true, seed: null })} />
        <Box sx={{ textAlign: 'right', mt: 0.75 }}>
          <Link component="button" variant="body2" onClick={onManage}>Manage trees</Link>
        </Box>
        <UpdateNotice dataset={dataset} title={shortTitle(manifest)} />

        <Typography sx={{ textAlign: 'center', mt: 3, mb: 1.5, fontFamily: FONT_DISPLAY, fontSize: '1.15rem' }}>
          {manifest.prompt}
        </Typography>
        {sizes && size !== null && (
          <SizeSlider
            sizes={sizes} size={size} plural={plural} leaves={leafCount(dataset)}
            onChange={(next) => next !== size && onSwitch(dataset, { landing: true, seed: null }, next)}
          />
        )}
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5} sx={{ justifyContent: 'center' }}>
          {resumable && roundMode === 'practice' && (
            <Button variant="contained" size="large" onClick={resume}>Resume your round</Button>
          )}
          <Button
            variant={(resumable && roundMode === 'practice') || doneToday ? 'outlined' : 'contained'}
            size="large"
            onClick={openDaily}
          >
            {dailyResumable ? `Resume today’s ${leaf}` : `Today’s ${leaf}${doneToday ? ' ✓' : ''}`}
          </Button>
          <Button variant="outlined" size="large" onClick={() => startGame('practice')}>
            Practice
          </Button>
          <Button variant="outlined" size="large" onClick={() => setMode('odd')}>
            Odd one out
          </Button>
          <Button variant="outlined" size="large" onClick={() => setMode('lineup')}>
            Line-up
          </Button>
          <Button variant="outlined" size="large" onClick={() => setMode('explore')}>
            Explore
          </Button>
        </Stack>
        <Typography variant="body2" sx={{ mt: 1.5, textAlign: 'center', color: 'text.secondary' }}>
          Odd one out is ten quick puzzles: of three {plural}, which two share a
          group the third is not in? Line-up is five: put four in order of
          kinship to a fifth. Explore has no secret and nothing to guess.
          {' '}<Link component="button" variant="body2" onClick={() => setStatsOpen(true)} sx={{ verticalAlign: 'baseline' }}>Your stats</Link>
        </Typography>
        <StatsDialog open={statsOpen} onClose={() => setStatsOpen(false)} dataset={daily} title={shortTitle(manifest)} />

        {/* Set apart: a different job from starting a round. */}
        <Box sx={{ mt: 4, pt: 3, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="body2" sx={{ mb: 1.5, textAlign: 'center', color: 'text.secondary' }}>
            Got a seed from someone? Play their exact round.
          </Typography>
          <Stack direction="row" spacing={1} sx={{ justifyContent: 'center', alignItems: 'flex-start' }}>
            <TextField
              size="small"
              placeholder="ABCD-234567"
              value={seedInput}
              onChange={(e) => { setSeedInput(e.target.value); setSeedError(null); setSeedElsewhere(null) }}
              onKeyDown={(e) => { if (e.key === 'Enter' && seedInput.trim()) void startGame('practice', seedInput.trim()) }}
              error={Boolean(seedError)}
              slotProps={{ htmlInput: { 'aria-label': 'Seed', spellCheck: false, style: { fontFamily: 'ui-monospace, monospace', letterSpacing: '0.06em' } } }}
              sx={{ width: 210 }}
            />
            <Button variant="outlined" disabled={!seedInput.trim()} onClick={() => startGame('practice', seedInput.trim())} sx={{ height: 40 }}>
              Play seed
            </Button>
          </Stack>
          {seedError && (
            <Alert severity="error" sx={{ mt: 2 }}>
              {seedError}
              {seedElsewhere && <>
                {' '}
                <Link component="button" onClick={() => onSwitch(seedElsewhere.id, { landing: false, seed: seedElsewhere.seed }, seedElsewhere.size ?? undefined)}>
                  Play it there
                </Link>
              </>}
            </Alert>
          )}
        </Box>

        <Sources manifest={manifest} />
      </Box>
    </Box>
  )

  if (mode === 'odd') return (
    <Box sx={{ p: PAGE_PAD, height: '100dvh', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', '& > *': { flexShrink: 0 } }}>
      {header(sized('Odd one out'))}
      <OddOneOut dataset={game} title={shortTitle(manifest)} plural={plural} linkSeed={oddLink} />
    </Box>
  )

  if (mode === 'lineup') return (
    <Box sx={{ p: PAGE_PAD, height: '100dvh', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', '& > *': { flexShrink: 0 } }}>
      {header(sized('Line-up'))}
      <LineUp dataset={game} title={shortTitle(manifest)} plural={plural} linkSeed={lineupLink} />
    </Box>
  )

  if (mode === 'explore') return (
    <Box sx={{ p: PAGE_PAD, height: '100dvh', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', '& > *': { flexShrink: 0 } }}>
      {header(sized('Explore'))}
      <Suspense fallback={treeFallback}><ExploreTree /></Suspense>
    </Box>
  )

  // Won or gave up: either way the round is finished and nothing more can be guessed.
  const over = won || revealed
  const closest = closestGuess(treeData, manifest)
  const score = guesses.length + hintPoints
  const nextHintCost = hintCost(score)
  const newRound = mode === 'practice' && (
    <Button variant="outlined" onClick={() => startGame('practice')}>New {leaf}</Button>
  )
  // How the round went, as squares that give nothing away; and for a daily,
  // where it leaves the streak.
  const afterRound = <>
    <Button variant={mode === 'daily' ? 'contained' : 'text'} onClick={shareResult}>
      {resultSharer.copied ? 'Copied' : canShareSheet ? 'Share result' : 'Copy result'}
    </Button>
    {mode === 'daily' && <Button variant="outlined" onClick={() => setStatsOpen(true)}>Stats</Button>}
    {newRound}
  </>

  return (
    // A column exactly the screen's height, so the tree takes whatever the
    // controls leave. Nothing else shrinks: on a screen too short for
    // everything the page scrolls instead of squashing the guess list.
    <Box sx={{ p: PAGE_PAD, height: '100dvh', boxSizing: 'border-box', display: 'flex', flexDirection: 'column', '& > *': { flexShrink: 0 } }}>
      {header(sized(mode === 'daily' ? 'Daily' : 'Practice'), mode === 'practice' && (
        // "New" alone on a phone: "New instrument" beside "Instruments" took the
        // header to two rows at 390px, where TaxoQuiz's "New animal" fitted.
        <Button size="small" sx={{ whiteSpace: 'nowrap' }} aria-label={`New ${leaf}`} onClick={() => startGame('practice')}>
          {narrow ? 'New' : `New ${leaf}`}
        </Button>
      ))}

      {(seed || !over) && (
        <Stack direction="row" spacing={1} useFlexGap sx={{ mb: { xs: 1, sm: 2 }, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
          {seed && <>
            {/* The word goes on a phone, where the row has no room for it and
              * the code in its chip already looks like what it is. */}
            <Typography variant="caption" sx={{ color: 'text.secondary', letterSpacing: '0.08em', textTransform: 'uppercase', display: { xs: 'none', sm: 'inline' } }}>Seed</Typography>
            <Chip label={seed} size="small" variant="outlined" sx={{ fontFamily: 'ui-monospace, monospace', fontWeight: 600, letterSpacing: '0.06em' }} />
            <Tooltip title={roundSharer.copied ? 'Copied' : 'Copy a link to this round'} open={roundSharer.copied || undefined}>
              <Button size="small" sx={SEED_ROW_BUTTON} onClick={shareRound}>{roundSharer.copied ? 'Copied' : canShareSheet ? 'Share' : 'Copy link'}</Button>
            </Tooltip>
            <Typography variant="caption" sx={{ color: 'text.secondary', display: { xs: 'none', sm: 'inline' }, fontFamily: FONT_DISPLAY, fontStyle: 'italic', fontSize: '0.85rem' }}>
              share this to let someone play the same round
            </Typography>
          </>}
          {/* The far end of the seed row rather than a line of its own: a whole
            * row of a phone's screen for controls pressed once a round. */}
          <Box sx={{ flex: 1, minWidth: 0 }} />
          {!over && (
            <Button size="small" variant="text" sx={SEED_ROW_BUTTON} disabled={!hintAvailable(treeData)} onClick={() => setConfirmHint(true)}>
              Hint +{nextHintCost}
            </Button>
          )}
          {!over && <Button size="small" variant="text" sx={SEED_ROW_BUTTON} onClick={() => setConfirmGiveUp(true)}>Give up</Button>}
        </Stack>
      )}

      {!over && (
        <GuessInput
          onGuess={(label) => guessAll([label])}
          onBulkGuess={guessAll}
          bulk={bulkScope(treeData, bulkUnlock(manifest), manifest)}
          disabled={over}
          exclude={guesses}
          noun={leaf}
        />
      )}
      {won && (
        <Stack direction="row" spacing={2} useFlexGap sx={{ mt: 1, alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
          <Typography variant="h5" sx={{ color: 'success.dark' }}>
            You got it in {score} {hintPoints > 0
              ? `(${guesses.length} ${guesses.length === 1 ? 'guess' : 'guesses'} + ${hintPoints} for ${hints === 1 ? 'a hint' : `${hints} hints`})`
              : guesses.length === 1 ? 'guess' : 'guesses'} — the answer was{' '}
            <Box component="em" sx={{ fontStyle: 'italic' }}>{displayName(secret ?? '')}</Box>
          </Typography>
          {afterRound}
        </Stack>
      )}
      {revealed && !won && (
        <Stack direction="row" spacing={2} useFlexGap sx={{ mt: 1, alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
          {/* Stated, not celebrated: success green would congratulate the one
            * outcome that is not a success. */}
          <Typography variant="h5" sx={{ color: 'text.secondary' }}>
            The answer was{' '}
            <Box component="em" sx={{ fontStyle: 'italic', color: 'text.primary' }}>{displayName(secret ?? '')}</Box>
          </Typography>
          {afterRound}
        </Stack>
      )}
      {revealed && !won && closest && (
        <Typography variant="body1" sx={{ mt: 0.5, color: 'text.secondary' }}>{describeClosest(closest)}</Typography>
      )}

      <GuessList guesses={guesses} secret={secret} />

      <Box sx={{ mt: { xs: 1, sm: 2 }, ...TREE_BLEED, flex: '1 0 0', minHeight: { xs: 300, sm: 400 } }}>
        <Suspense fallback={treeFallback}>
          <GameTree
            treeData={treeData}
            focusLabel={hintFocus ? '???' : guesses[guesses.length - 1] ?? null}
            newestLabel={guesses[guesses.length - 1] ?? null}
          />
        </Suspense>
      </Box>

      <StatsDialog open={statsOpen} onClose={() => setStatsOpen(false)} dataset={daily} title={shortTitle(manifest)} />
      {/* A shared link arriving mid-round: asked, because opening a link is not
        * a decision to throw away a daily in progress. */}
      <Dialog open={pendingLink !== null} onClose={() => setPendingLink(null)}>
        <DialogTitle>Play the shared round?</DialogTitle>
        <DialogContent>
          <DialogContentText>You have a round in progress. Starting the one from the link ends it.</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingLink(null)}>Keep my round</Button>
          <Button onClick={() => { const s = pendingLink!; setPendingLink(null); void startGame('practice', s) }} autoFocus>
            Play the link
          </Button>
        </DialogActions>
      </Dialog>
      {/* Confirmed: on a daily there is no second go, and the button sits a few
        * pixels from the one pressed all round. */}
      <Dialog open={confirmGiveUp} onClose={() => setConfirmGiveUp(false)}>
        <DialogTitle>Give up and see the answer?</DialogTitle>
        <DialogActions>
          <Button onClick={() => setConfirmGiveUp(false)}>Keep playing</Button>
          <Button onClick={() => { setRevealed(true); setConfirmGiveUp(false) }} autoFocus>Show me</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={confirmHint} onClose={() => setConfirmHint(false)}>
        <DialogTitle>Take a hint?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            It reveals the next group the answer belongs to, and adds {nextHintCost} to
            your score: {score} → {score + nextHintCost}.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmHint(false)}>Keep playing</Button>
          <Button onClick={takeHint} autoFocus>Reveal (+{nextHintCost})</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

/** A big tree with a newer version out. Small ones update themselves; a big
 *  one waits to be asked, and the copy here plays until then — a round in
 *  progress keeps the tree its seed was dealt on. */
function UpdateNotice({ dataset, title }: { dataset: string; title: string }) {
  const t = useTree(dataset)
  if (!t?.big || !t.update || !t.offer) return null
  return (
    <Alert
      severity="info"
      sx={{ mt: 2 }}
      action={!t.progress && (
        <Button color="inherit" size="small" onClick={() => void download(dataset).catch(() => {})}>
          Update ({formatBytes(t.offer.gzip)})
        </Button>
      )}
    >
      A newer {title} is out. The copy on this device plays until you update, and a round in progress may not survive the change.
      {t.progress && <Progress p={t.progress} />}
      {t.error && <Box sx={{ color: 'error.main' }}>{t.error}</Box>}
    </Alert>
  )
}

/** Where a tree came from, under its licence. Shown on the front page because
 *  the licences ask for attribution where the data is used, and this is where
 *  every round starts. */
function Sources({ manifest }: { manifest: Manifest }) {
  if (!manifest.sources?.length) return null
  return (
    <Box sx={{ mt: 4, color: 'text.secondary' }}>
      {manifest.sources.map((s) => (
        <Typography key={s.name} variant="caption" sx={{ display: 'block', textAlign: 'center', lineHeight: 1.5, mb: 0.5 }}>
          <Link href={s.url} target="_blank" rel="noopener">{s.name}</Link>
          {s.licence && <>{' · '}{s.licence_url ? <Link href={s.licence_url} target="_blank" rel="noopener">{s.licence}</Link> : s.licence}</>}
          {s.note && <>{' — '}{s.note}</>}
        </Typography>
      ))}
    </Box>
  )
}
