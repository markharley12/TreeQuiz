/**
 * Line-up: five puzzles of a target and four others, put in order of how
 * near each sits to the target in the tree. See `treequiz/lineup.py` for why
 * each has exactly one right order and how a set gets harder as it goes.
 *
 * Tapping a name gives it the next place; tapping a placed name takes it and
 * everything after it back. The last name has only one place left, so it
 * takes it. The answer is drawn as a ladder down the target's lineage.
 */
import { useEffect, useState } from 'react'
import { Alert, Box, Button, ButtonBase, Chip, CircularProgress, Stack, Typography } from '@mui/material'
import { fetchLineUpLadder, startLineUp, type Ladder, type LineUp as Puzzle } from '../api'
import { OPTIONS, SET_SIZE, score } from '../engine/lineup'
import { ordinal } from '../lineupReveal'
import { displayName } from '../names'
import { lineUpShareText, setStreak } from '../setStore'
import { useSetGame } from '../setGame'
import { shareBase, shareLink } from '../shareLink'
import { ACCENT, CARD, FONT_DISPLAY, INK, INK_MUTED, LINE } from '../theme'
import InfoPopup from './InfoPopup'
import LineUpLadder from './LineUpLadder'
import { SetHeader, SetProgress, SetSummary } from './SetParts'

interface Props {
  dataset: string
  title: string
  /** What a leaf is called in the plural: "cities". */
  plural: string
  /** A set's seed from a link, to deal instead of resuming. */
  linkSeed: string | null
}

/** A set runs easy to hard; see `treequiz/lineup.py`. */
const TIERS = ['Easy', 'Medium', 'Hard']

export default function LineUp({ dataset, title, plural, linkSeed }: Props) {
  const game = useSetGame<Puzzle, string[]>({ game: 'lineup', dataset, linkSeed, size: SET_SIZE, start: startLineUp, points: score })
  const { set, shown, puzzle, answered, today, day, dailies, tally } = game
  const key = set ? `${set.seed}:${shown}` : ''
  // The order being built, for the puzzle it was built on.
  const [draft, setDraft] = useState<{ key: string; picks: string[] }>({ key: '', picks: [] })
  const picks = answered ? game.given! : draft.key === key ? draft.picks : []
  const [ladder, setLadder] = useState<{ key: string; l: Ladder } | null>(null)
  const shownLadder = ladder?.key === key ? ladder.l : null
  const [popup, setPopup] = useState<string | null>(null)

  useEffect(() => {
    if (!answered || !puzzle) return
    let cancelled = false
    const forKey = key
    fetchLineUpLadder(dataset, puzzle).then((l) => { if (!cancelled) setLadder({ key: forKey, l }) }).catch(() => {})
    return () => { cancelled = true }
  }, [answered, key]) // eslint-disable-line react-hooks/exhaustive-deps

  function place(next: string[]) {
    if (!puzzle) return
    // The last one has only one place left.
    if (next.length === OPTIONS - 1) next = [...next, puzzle.choices.find((c) => !next.includes(c))!]
    setDraft({ key, picks: next })
  }

  function tap(label: string) {
    if (answered || !puzzle) return
    const at = picks.indexOf(label)
    place(at >= 0 ? picks.slice(0, at) : [...picks, label])
  }

  // Undoing a full order takes the fourth back with the third, which only
  // went where it went because the third did.
  const undo = () => place(picks.slice(0, picks.length === OPTIONS ? OPTIONS - 2 : Math.max(0, picks.length - 1)))
  const check = () => { if (picks.length === OPTIONS) game.answer(picks) }

  // 1–4 to place; Backspace to take one back; Enter to check, then for the
  // next. A key used here is used up: Enter's own press would otherwise land
  // on the Next button that checking puts under focus, and skip the answer.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || popup || !puzzle) return
      if (!answered && ['1', '2', '3', '4'].includes(e.key)) tap(puzzle.choices[Number(e.key) - 1])
      else if (!answered && e.key === 'Backspace') undo()
      else if (!answered && e.key === 'Enter') check()
      else if (answered && (e.key === 'Enter' || e.key === 'ArrowRight')) game.advance()
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const link = () => shareLink(shareBase(window.location.href), dataset, set!.seed, 'lineup')

  if (game.error) return (
    <Box sx={{ mt: 2 }}>
      <Alert severity="error" sx={{ mb: 2 }}>{game.error}</Alert>
      <Button variant="contained" onClick={() => game.deal()}>Deal a new set</Button>
    </Box>
  )
  if (!set) return <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}><CircularProgress /></Box>

  const outOf = SET_SIZE * OPTIONS
  const total = game.scores.reduce((a, b) => a + b, 0)
  const rows = game.answers.map((a, i) => a.map((label, k) => label === set.puzzles[i].order[k]))
  const got = answered && puzzle ? score(puzzle, picks) : 0

  return (
    <Box sx={{ overflowY: 'auto', flex: '1 0 0', minHeight: 0, pb: 3 }}>
      <SetHeader
        seed={set.seed} link={link} offerToday={day !== today} todayDone={Boolean(dailies[today])}
        onToday={() => game.deal(game.todays())} onNew={() => game.deal()}
      />

      <SetProgress scores={game.scores} max={OPTIONS} size={SET_SIZE} shown={shown} today={day === today} />

      {game.over ? (
        <SetSummary
          score={total} outOf={outOf} verdict={verdict(total, outOf)}
          marks={(
            <Box aria-label="Your places" sx={{ fontSize: '1.2rem', mt: 2, lineHeight: 1.3, letterSpacing: '0.08em' }}>
              {rows.map((row, i) => <div key={i}>{row.map((ok) => (ok ? '🟩' : '🟥')).join('')}</div>)}
            </Box>
          )}
          shareText={() => lineUpShareText(title, rows, link(), day ?? undefined)}
          onAnother={() => game.deal()}
          tallyText={tally.sets === 0 ? null : (tally.sets === 1 ? 'Your first set on this tree.'
            : `${tally.sets} sets on this tree: ${(tally.right / tally.sets).toFixed(1)} of ${outOf} in place on average, best ${tally.best}.`)
            + (setStreak(dailies, today) > 1 ? ` Today’s set ${setStreak(dailies, today)} days running.` : '')}
          offerToday={day !== today && !dailies[today]}
          onToday={() => game.deal(game.todays())}
        />
      ) : puzzle && (
        <>
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', mt: 2 }}>
            <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: { xs: '1.25rem', sm: '1.5rem' } }}>
              Nearest first
            </Typography>
            <Chip size="small" variant="outlined" label={TIERS[puzzle.tier]} />
          </Stack>
          <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
            Tap these four {plural} in order of how near they sit to {displayName(puzzle.target)} in the tree, nearest first.
          </Typography>

          <Box sx={{ mb: 1.5, px: 2, py: 1.25, borderRadius: 2, bgcolor: CARD, border: `2px solid ${ACCENT}`, display: 'flex', alignItems: 'baseline', gap: 1.25 }}>
            <Typography component="span" sx={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: ACCENT }}>
              Target
            </Typography>
            <Typography component="span" sx={{ fontFamily: FONT_DISPLAY, fontWeight: 700, fontSize: { xs: '1.15rem', sm: '1.3rem' }, color: INK, overflowWrap: 'anywhere' }}>
              {displayName(puzzle.target)}
            </Typography>
          </Box>

          <Box sx={{ display: 'grid', gap: 1.25, gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)' } }}>
            {puzzle.choices.map((label) => {
              const at = picks.indexOf(label)
              const right = answered && puzzle.order[at] === label
              const state = !answered ? (at >= 0 ? 'placed' : 'open') : right ? 'right' : 'wrong'
              return (
                <ButtonBase
                  key={label}
                  disabled={answered}
                  onClick={() => tap(label)}
                  aria-label={`${displayName(label)}${at >= 0 ? `, placed ${ordinal(at)}` : ''}`}
                  sx={{
                    display: 'flex', alignItems: 'center', gap: 1.25, textAlign: 'left', justifyContent: 'flex-start',
                    p: { xs: 1.25, sm: 1.75 }, minHeight: { xs: 52, sm: 72 }, borderRadius: 2, bgcolor: CARD,
                    border: '1px solid', borderWidth: state === 'open' ? 1 : 2,
                    borderColor: state === 'right' ? 'success.main' : state === 'wrong' ? 'error.main' : state === 'placed' ? INK : LINE,
                    boxShadow: '0 1px 2px rgba(44,38,32,0.08)',
                    transition: 'border-color 120ms, box-shadow 120ms',
                    '&:hover': answered ? {} : { borderColor: ACCENT, boxShadow: `0 0 0 1px ${ACCENT}` },
                  }}
                >
                  <Box component="span" sx={{
                    flex: 'none', width: 28, height: 28, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: '0.9rem',
                    bgcolor: state === 'right' ? 'success.main' : state === 'wrong' ? 'error.main' : state === 'placed' ? INK : 'transparent',
                    color: state === 'open' ? INK_MUTED : '#fff',
                    border: state === 'open' ? `1.5px dashed ${LINE}` : 'none',
                  }}>
                    {at >= 0 ? at + 1 : ''}
                  </Box>
                  <Typography component="span" sx={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: { xs: '1.05rem', sm: '1.15rem' }, color: INK, overflowWrap: 'anywhere' }}>
                    {displayName(label)}
                  </Typography>
                  {state === 'wrong' && (
                    <Box component="span" sx={{ ml: 'auto', color: 'error.dark', fontWeight: 700, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                      {ordinal(puzzle.order.indexOf(label))}
                    </Box>
                  )}
                  {state === 'right' && <Box component="span" sx={{ ml: 'auto', color: 'success.dark', fontWeight: 700 }}>✓</Box>}
                </ButtonBase>
              )
            })}
          </Box>

          {!answered ? (
            <Stack direction="row" spacing={1.5} sx={{ mt: 2, alignItems: 'center' }}>
              <Button variant="contained" disabled={picks.length < OPTIONS} onClick={check}>Check</Button>
              <Button disabled={picks.length === 0} onClick={undo}>Undo</Button>
            </Stack>
          ) : (
            <Box sx={{ mt: 2.5 }}>
              <Stack direction="row" spacing={2} useFlexGap sx={{ alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
                <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '1.3rem', color: got === OPTIONS ? 'success.dark' : 'text.primary' }}>
                  {got === OPTIONS ? 'All four in place.' : `${got} of ${OPTIONS} in place.`}
                </Typography>
                <Box sx={{ flex: 1 }} />
                <Button variant="contained" onClick={game.advance} autoFocus>
                  {shown + 1 < SET_SIZE ? 'Next' : 'See your score'}
                </Button>
              </Stack>
              {shownLadder && (
                <>
                  <Typography variant="body2" sx={{ color: 'text.secondary', mt: 1, mb: 2 }}>
                    Down the tree to {displayName(puzzle.target)}: each joins it where it hangs off. Tap any name to read about it.
                  </Typography>
                  <Box sx={{ maxWidth: 560, mx: 'auto' }}>
                    <LineUpLadder ladder={shownLadder} placed={new Map(picks.map((p, i) => [p, i]))} onOpen={setPopup} />
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

function verdict(points: number, outOf: number): string {
  if (points === outOf) return 'Every one in place. You know this tree.'
  if (points >= outOf * 0.8) return 'Very good — the last ones are hard.'
  if (points >= outOf / 2) return 'Not bad. The ladders are worth a look.'
  return 'A tricky set. Each ladder shows the tree, and the next set will go better.'
}
