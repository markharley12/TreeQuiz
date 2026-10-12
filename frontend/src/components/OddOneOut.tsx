/**
 * Odd one out: ten puzzles of three leaves, two of which share a group the
 * third is not in. See `treequiz/odd.py` for why each has exactly one answer
 * and how a set gets harder as it goes.
 *
 * The answer is shown as the tree of the three — where they meet, and where
 * the pair parts from the odd one — which is the point of the game: a set is
 * ten small lessons in the shape of the tree.
 */
import { useEffect, useState } from 'react'
import { Alert, Box, Button, ButtonBase, Chip, CircularProgress, Stack, Tooltip, Typography } from '@mui/material'
import { fetchOddReveal, startOddSet, type OddSet, type Reveal } from '../api'
import { SET_SIZE } from '../engine/odd'
import { normalise } from '../engine/seed'
import { displayName } from '../names'
import { because } from '../oddReveal'
import { oddShareText, readOddSession, readOddTally, recordOddSet, writeOddSession, type OddTally } from '../oddStore'
import { shareBase, shareLink } from '../shareLink'
import { useSharer } from '../sharer'
import { ACCENT, CARD, FONT_DISPLAY, INK, INK_MUTED, LINE } from '../theme'
import OddFork, { type LeafMark } from './OddFork'
import InfoPopup from './InfoPopup'

interface Props {
  dataset: string
  title: string
  /** What a leaf is called in the plural: "cities". */
  plural: string
  /** A set's seed from a link, to deal instead of resuming. */
  linkSeed: string | null
}

/** A set runs easy to hard; see `treequiz/odd.py`. */
const TIERS = ['Easy', 'Medium', 'Hard']
const SEED_CHIP = { fontFamily: 'ui-monospace, monospace', fontWeight: 600, letterSpacing: '0.06em' } as const

export default function OddOneOut({ dataset, title, plural, linkSeed }: Props) {
  const [set, setSet] = useState<OddSet | null>(null)
  const [answers, setAnswers] = useState<string[]>([])
  // The puzzle on screen. Behind `answers` by one while an answer is shown.
  const [shown, setShown] = useState(0)
  const [reveal, setReveal] = useState<Reveal | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [popup, setPopup] = useState<string | null>(null)
  const [tally, setTally] = useState<OddTally>(() => readOddTally(dataset))
  const linkSharer = useSharer()
  const resultSharer = useSharer()

  function show(next: OddSet, resumed: string[]) {
    setError(null)
    setReveal(null)
    setSet(next)
    setAnswers(resumed)
    setShown(Math.min(resumed.length, SET_SIZE))
    writeOddSession(dataset, { seed: next.seed, answers: resumed })
    if (resumed.length >= SET_SIZE) countSet(next, resumed)
  }

  const failed = (e: unknown) => setError(e instanceof Error ? e.message : 'Could not deal that set')

  function deal(seed?: string, resumed: string[] = []) {
    startOddSet(dataset, { seed }).then((next) => show(next, resumed), failed)
  }

  // On arrival: a link's set, else the set in progress, else a new one. Called
  // off, so a remount deals once rather than twice.
  useEffect(() => {
    const saved = readOddSession(dataset)
    const [seed, resumed] = linkSeed !== null
      ? [linkSeed, saved && sameSeed(saved.seed, linkSeed) ? saved.answers : []]
      : saved ? [saved.seed, saved.answers] : [undefined, []]
    let cancelled = false
    startOddSet(dataset, { seed }).then(
      (next) => { if (!cancelled) show(next, resumed) },
      (e) => { if (!cancelled) failed(e) },
    )
    return () => { cancelled = true }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const puzzle = set && shown < SET_SIZE ? set.puzzles[shown] : null
  const answered = puzzle !== null && answers.length > shown
  const picked = answered ? answers[shown] : null

  // The answer's tree, once there is an answer to explain.
  useEffect(() => {
    if (!answered || !puzzle) return
    let cancelled = false
    fetchOddReveal(dataset, puzzle).then((r) => { if (!cancelled) setReveal(r) }).catch(() => {})
    return () => { cancelled = true }
  }, [answered, shown, set]) // eslint-disable-line react-hooks/exhaustive-deps

  const marks = set ? answers.map((a, i) => a === set.puzzles[i].odd) : []
  const right = marks.filter(Boolean).length
  const over = set !== null && shown >= SET_SIZE

  // A finished set counts toward the tally once per seed, whether it was
  // finished just now or found finished on a reload.
  function countSet(of: OddSet, given: string[]) {
    setTally(recordOddSet(dataset, of.seed, given.filter((a, i) => a === of.puzzles[i].odd).length))
  }

  function choose(label: string) {
    if (!set || answered || !puzzle) return
    const next = [...answers, label]
    setAnswers(next)
    setReveal(null)
    writeOddSession(dataset, { seed: set.seed, answers: next })
  }

  function advance() {
    setReveal(null)
    setShown(shown + 1)
    if (set && shown + 1 >= SET_SIZE) countSet(set, answers)
  }

  // 1, 2, 3 to choose; Enter or → for the next one.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || popup) return
      if (!answered && puzzle && ['1', '2', '3'].includes(e.key)) choose(puzzle.choices[Number(e.key) - 1])
      else if (answered && (e.key === 'Enter' || e.key === 'ArrowRight')) advance()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const link = () => shareLink(shareBase(window.location.href), dataset, set!.seed, 'odd')

  if (error) return (
    <Box sx={{ mt: 2 }}>
      <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      <Button variant="contained" onClick={() => deal()}>Deal a new set</Button>
    </Box>
  )
  if (!set) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}><CircularProgress /></Box>

  // The reveal marks the odd one, and the pick if it was not; a leaf box's
  // text is its label, which is what was picked.
  const markOf = new Map<string, LeafMark>()
  if (reveal && puzzle) {
    markOf.set(reveal.odd.name, 'odd')
    const wrong = picked !== puzzle.odd ? reveal.pair.find((b) => b.text === picked) : undefined
    if (wrong) markOf.set(wrong.name, 'wrong')
  }

  return (
    <Box sx={{ overflowY: 'auto', flex: '1 0 0', minHeight: 0, pb: 3 }}>
      <Stack direction="row" spacing={1} useFlexGap sx={{ mb: 1.5, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
        <Chip label={set.seed} size="small" variant="outlined" sx={SEED_CHIP} />
        <Tooltip title={linkSharer.copied ? 'Copied' : 'Copy a link to this set'} open={linkSharer.copied || undefined}>
          <Button size="small" onClick={() => void linkSharer.share({ url: link() })}>
            {linkSharer.copied ? 'Copied' : linkSharer.canShareSheet ? 'Share' : 'Copy link'}
          </Button>
        </Tooltip>
        <Box sx={{ flex: 1 }} />
        <Button size="small" onClick={() => deal()}>New set</Button>
      </Stack>

      <Progress marks={marks} shown={shown} />

      {over ? (
        <Box sx={{ textAlign: 'center', mt: 4 }}>
          <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '2.6rem', lineHeight: 1.1 }}>{right} of {SET_SIZE}</Typography>
          <Typography sx={{ color: 'text.secondary', mt: 1 }}>{verdict(right)}</Typography>
          <Typography aria-label="Your marks" sx={{ fontSize: '1.4rem', mt: 2, letterSpacing: '0.1em' }}>
            {marks.map((m) => (m ? '✅' : '❌')).join('')}
          </Typography>
          <Stack direction="row" spacing={1.5} useFlexGap sx={{ justifyContent: 'center', mt: 3, flexWrap: 'wrap', rowGap: 1 }}>
            <Button variant="contained" onClick={() => void resultSharer.share({ text: oddShareText(title, marks, link()) })}>
              {resultSharer.copied ? 'Copied' : resultSharer.canShareSheet ? 'Share result' : 'Copy result'}
            </Button>
            <Button variant="outlined" onClick={() => deal()}>Another set</Button>
          </Stack>
          {tally.sets > 0 && (
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 3 }}>
              {tally.sets === 1 ? 'Your first set on this tree.' : `${tally.sets} sets on this tree: ${(tally.right / tally.sets).toFixed(1)} right on average, best ${tally.best}.`}
            </Typography>
          )}
        </Box>
      ) : puzzle && (
        <>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 2 }}>
            <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
              Which is the odd one out?
            </Typography>
            <Chip size="small" variant="outlined" label={TIERS[puzzle.tier]} />
          </Stack>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
            Two of these {plural} share a group the third is not in.
          </Typography>
          <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', sm: 'repeat(3, 1fr)' } }}>
            {puzzle.choices.map((label, k) => {
              const isOdd = label === puzzle.odd
              const state = !answered ? 'open' : isOdd ? 'odd' : label === picked ? 'wrong' : 'pair'
              return (
                <ButtonBase
                  key={label}
                  disabled={answered}
                  onClick={() => choose(label)}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1.25, textAlign: 'left', justifyContent: 'flex-start',
                    p: { xs: 1.5, sm: 2 }, minHeight: { xs: 56, sm: 88 }, borderRadius: 2, bgcolor: CARD,
                    border: '1px solid', borderColor: state === 'odd' ? 'success.main' : state === 'wrong' ? 'error.main' : LINE,
                    borderWidth: state === 'odd' || state === 'wrong' ? 2 : 1,
                    opacity: state === 'pair' ? 0.7 : 1,
                    boxShadow: '0 1px 2px rgba(44,38,32,0.08)',
                    transition: 'border-color 120ms, box-shadow 120ms',
                    '&:hover': answered ? {} : { borderColor: ACCENT, boxShadow: `0 0 0 1px ${ACCENT}` },
                  }}
                >
                  <Box component="span" sx={{ color: INK_MUTED, fontSize: '0.8rem', fontWeight: 700, display: { xs: 'none', sm: 'inline' } }}>{k + 1}</Box>
                  <Typography component="span" sx={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: { xs: '1.05rem', sm: '1.2rem' }, color: INK, overflowWrap: 'anywhere' }}>
                    {displayName(label)}
                  </Typography>
                  {state === 'odd' && <Box component="span" sx={{ ml: 'auto', color: 'success.dark', fontWeight: 700 }}>✓</Box>}
                  {state === 'wrong' && <Box component="span" sx={{ ml: 'auto', color: 'error.dark', fontWeight: 700 }}>✗</Box>}
                </ButtonBase>
              )
            })}
          </Box>

          {answered && (
            <Box sx={{ mt: 2.5 }}>
              <Stack direction="row" spacing={2} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
                <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '1.3rem', color: picked === puzzle.odd ? 'success.dark' : 'text.primary' }}>
                  {picked === puzzle.odd ? 'Right.' : `Not quite — it was ${displayName(puzzle.odd)}.`}
                </Typography>
                <Box sx={{ flex: 1 }} />
                <Button variant="contained" onClick={advance} autoFocus>
                  {shown + 1 < SET_SIZE ? 'Next' : 'See your score'}
                </Button>
              </Stack>
              {reveal && (
                <>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mt: 1, mb: 2 }}>
                    {because(puzzle, reveal, displayName)} Tap any name to read about it.
                  </Typography>
                  <Box sx={{ maxWidth: 640, mx: 'auto' }}>
                    <OddFork reveal={reveal} marks={markOf} onOpen={setPopup} />
                  </Box>
                </>
              )}
            </Box>
          )}
        </>
      )}
      {popup && <InfoPopup names={[popup]} onClose={() => setPopup(null)} />}
    </Box>
  )
}

/** Ten dots: right, wrong, the one on screen, and those to come. */
function Progress({ marks, shown }: { marks: boolean[]; shown: number }) {
  return (
    <Stack direction="row" spacing={0.75} aria-label={`Puzzle ${Math.min(shown + 1, SET_SIZE)} of ${SET_SIZE}`} sx={{ alignItems: 'center' }}>
      {Array.from({ length: SET_SIZE }, (_, i) => {
        const done = i < marks.length
        return (
          <Box
            key={i}
            sx={{
              width: 14, height: 14, borderRadius: '50%', boxSizing: 'border-box',
              bgcolor: done ? (marks[i] ? 'success.main' : 'error.main') : 'transparent',
              border: done ? 'none' : `2px solid ${i === shown ? INK : LINE}`,
            }}
          />
        )
      })}
      <Typography variant="caption" sx={{ pl: 1, color: 'text.secondary' }}>
        {Math.min(shown + 1, SET_SIZE)} of {SET_SIZE}
      </Typography>
    </Stack>
  )
}

function verdict(right: number): string {
  if (right === SET_SIZE) return 'Every one. You know this tree.'
  if (right >= 8) return 'Very good — the last few are hard.'
  if (right >= 5) return 'Not bad. The answers are worth a look.'
  return 'A tricky set. Each answer shows the tree, and the next set will go better.'
}

function sameSeed(a: string, b: string): boolean {
  try {
    return normalise(a) === normalise(b)
  } catch {
    return false
  }
}
