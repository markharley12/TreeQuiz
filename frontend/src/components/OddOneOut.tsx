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
import { Alert, Box, Button, ButtonBase, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import { fetchOddReveal, startOddSet, type Puzzle, type Reveal } from '../api'
import { SET_SIZE } from '../engine/odd'
import { displayName } from '../names'
import { because } from '../oddReveal'
import { oddShareText, setStreak } from '../setStore'
import { useSetGame } from '../setGame'
import { shareBase, shareLink } from '../shareLink'
import { ACCENT, CARD, FONT_DISPLAY, INK, INK_MUTED, LINE } from '../theme'
import OddFork, { type LeafMark } from './OddFork'
import InfoPopup from './InfoPopup'
import { SetHeader, SetProgress, SetSummary } from './SetParts'

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

export default function OddOneOut({ dataset, title, plural, linkSeed }: Props) {
  const game = useSetGame<Puzzle, string>({
    game: 'odd', dataset, linkSeed, size: SET_SIZE, start: startOddSet,
    points: (p, picked) => (picked === p.odd ? 1 : 0),
  })
  const { set, shown, puzzle, answered, today, day, dailies, tally } = game
  const picked = game.given
  // The answer's tree, for the puzzle it was drawn for.
  const [reveal, setReveal] = useState<{ key: string; r: Reveal } | null>(null)
  const [popup, setPopup] = useState<string | null>(null)
  const revealKey = set ? `${set.seed}:${shown}` : ''
  const shownReveal = reveal?.key === revealKey ? reveal.r : null

  useEffect(() => {
    if (!answered || !puzzle) return
    let cancelled = false
    const key = revealKey
    fetchOddReveal(dataset, puzzle).then((r) => { if (!cancelled) setReveal({ key, r }) }).catch(() => {})
    return () => { cancelled = true }
  }, [answered, revealKey]) // eslint-disable-line react-hooks/exhaustive-deps

  const marks = game.scores.map((s) => s === 1)
  const right = marks.filter(Boolean).length

  // 1, 2, 3 to choose; Enter or → for the next one.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || popup) return
      if (!answered && puzzle && ['1', '2', '3'].includes(e.key)) game.answer(puzzle.choices[Number(e.key) - 1])
      else if (answered && (e.key === 'Enter' || e.key === 'ArrowRight')) game.advance()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const link = () => shareLink(shareBase(window.location.href), dataset, set!.seed, 'odd')

  if (game.error) return (
    <Box sx={{ mt: 2 }}>
      <Alert severity="error" sx={{ mb: 2 }}>{game.error}</Alert>
      <Button variant="contained" onClick={() => game.deal()}>Deal a new set</Button>
    </Box>
  )
  if (!set) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}><CircularProgress /></Box>

  // The reveal marks the odd one, and the pick if it was not; a leaf box's
  // text is its label, which is what was picked.
  const markOf = new Map<string, LeafMark>()
  if (shownReveal && puzzle) {
    markOf.set(shownReveal.odd.name, 'odd')
    const wrong = picked !== puzzle.odd ? shownReveal.pair.find((b) => b.text === picked) : undefined
    if (wrong) markOf.set(wrong.name, 'wrong')
  }

  return (
    <Box sx={{ overflowY: 'auto', flex: '1 0 0', minHeight: 0, pb: 3 }}>
      <SetHeader
        seed={set.seed} link={link} offerToday={day !== today} todayDone={Boolean(dailies[today])}
        onToday={() => game.deal(game.todays())} onNew={() => game.deal()}
      />

      <SetProgress scores={game.scores} max={1} size={SET_SIZE} shown={shown} today={day === today} />

      {game.over ? (
        <SetSummary
          score={right} outOf={SET_SIZE} verdict={verdict(right)}
          marks={(
            <Typography aria-label="Your marks" sx={{ fontSize: '1.4rem', mt: 2, letterSpacing: '0.1em' }}>
              {marks.map((m) => (m ? '✅' : '❌')).join('')}
            </Typography>
          )}
          shareText={() => oddShareText(title, marks, link(), day ?? undefined)}
          onAnother={() => game.deal()}
          tallyText={tally.sets === 0 ? null : (tally.sets === 1 ? 'Your first set on this tree.'
            : `${tally.sets} sets on this tree: ${(tally.right / tally.sets).toFixed(1)} right on average, best ${tally.best}.`)
            + (setStreak(dailies, today) > 1 ? ` Today’s set ${setStreak(dailies, today)} days running.` : '')}
          offerToday={day !== today && !dailies[today]}
          onToday={() => game.deal(game.todays())}
        />
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
                  onClick={() => game.answer(label)}
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
                <Button variant="contained" onClick={game.advance} autoFocus>
                  {shown + 1 < SET_SIZE ? 'Next' : 'See your score'}
                </Button>
              </Stack>
              {shownReveal && (
                <>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mt: 1, mb: 2 }}>
                    {because(puzzle, shownReveal, displayName)} Tap any name to read about it.
                  </Typography>
                  <Box sx={{ maxWidth: 640, mx: 'auto' }}>
                    <OddFork reveal={shownReveal} marks={markOf} onOpen={setPopup} />
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

function verdict(right: number): string {
  if (right === SET_SIZE) return 'Every one. You know this tree.'
  if (right >= 8) return 'Very good — the last few are hard.'
  if (right >= 5) return 'Not bad. The answers are worth a look.'
  return 'A tricky set. Each answer shows the tree, and the next set will go better.'
}
