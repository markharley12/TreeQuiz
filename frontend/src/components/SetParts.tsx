/**
 * What odd one out and line-up show alike: the row above a set (its seed, a
 * link to it, today's set, a new one), the dots of its progress, and the
 * score at the end. The puzzles themselves are each game's own.
 */
import type { ReactNode } from 'react'
import { Box, Button, Chip, Stack, Tooltip, Typography } from '@mui/material'
import { useSharer } from '../sharer'
import { FONT_DISPLAY, INK, LINE } from '../theme'

/** As the round's seed row: no 64px minimum and less padding on a phone, or
 *  four controls take two rows at 390px. */
const ROW_BUTTON = { whiteSpace: 'nowrap', minWidth: { xs: 0, sm: 64 }, paddingInline: { xs: '8px', sm: '18px' } } as const
const SEED_CHIP = { fontFamily: 'ui-monospace, monospace', fontWeight: 600, letterSpacing: '0.06em' } as const

interface HeaderProps {
  seed: string
  /** The set's link, made when it is shared. */
  link: () => string
  /** Offer today's set — not while it is the set on screen. */
  offerToday: boolean
  todayDone: boolean
  onToday: () => void
  onNew: () => void
}

export function SetHeader({ seed, link, offerToday, todayDone, onToday, onNew }: HeaderProps) {
  const sharer = useSharer()
  return (
    <Stack direction="row" spacing={1} useFlexGap sx={{ mb: 1.5, alignItems: 'center', flexWrap: 'wrap', rowGap: 0.5 }}>
      <Chip label={seed} size="small" variant="outlined" sx={SEED_CHIP} />
      <Tooltip title={sharer.copied ? 'Copied' : 'Copy a link to this set'} open={sharer.copied || undefined}>
        <Button size="small" sx={ROW_BUTTON} onClick={() => void sharer.share({ url: link() })}>
          {sharer.copied ? 'Copied' : sharer.canShareSheet ? 'Share' : 'Copy link'}
        </Button>
      </Tooltip>
      <Box sx={{ flex: 1 }} />
      {offerToday && (
        <Button size="small" sx={ROW_BUTTON} onClick={onToday}>
          Today’s set{todayDone ? ' ✓' : ''}
        </Button>
      )}
      <Button size="small" sx={ROW_BUTTON} onClick={onNew}>New set</Button>
    </Stack>
  )
}

interface ProgressProps {
  /** Each answered puzzle's points, in order. */
  scores: number[]
  /** A puzzle's most points: full marks are green, none red, between amber. */
  max: number
  size: number
  shown: number
  today: boolean
  /** "Puzzle", for the dots' label. */
  noun?: string
}

/** A dot per puzzle: how each went, the one on screen, and those to come. */
export function SetProgress({ scores, max, size, shown, today, noun = 'Puzzle' }: ProgressProps) {
  return (
    <Stack direction="row" spacing={0.75} aria-label={shown < size ? `${noun} ${shown + 1} of ${size}` : 'Set finished'} sx={{ alignItems: 'center' }}>
      {Array.from({ length: size }, (_, i) => {
        const done = i < scores.length
        const colour = !done ? 'transparent' : scores[i] >= max ? 'success.main' : scores[i] > 0 ? 'warning.main' : 'error.main'
        return (
          <Box
            key={i}
            sx={{
              width: 14, height: 14, borderRadius: '50%', boxSizing: 'border-box', bgcolor: colour,
              border: done ? 'none' : `2px solid ${i === shown ? INK : LINE}`,
            }}
          />
        )
      })}
      <Typography variant="caption" sx={{ pl: 1, color: 'text.secondary', whiteSpace: 'nowrap' }}>
        {shown < size && `${shown + 1} of ${size}`}
        {shown < size && today && ' · '}
        {today && 'Today’s set'}
      </Typography>
    </Stack>
  )
}

interface SummaryProps {
  score: number
  outOf: number
  verdict: string
  /** The set at a glance, as it is shared. */
  marks: ReactNode
  shareText: () => string
  onAnother: () => void
  /** A line about the sets played on this tree, if any. */
  tallyText: string | null
  /** Offer today's set, still to play. */
  offerToday: boolean
  onToday: () => void
}

export function SetSummary({ score, outOf, verdict, marks, shareText, onAnother, tallyText, offerToday, onToday }: SummaryProps) {
  const sharer = useSharer()
  return (
    <Box sx={{ textAlign: 'center', mt: 4 }}>
      <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '2.6rem', lineHeight: 1.1 }}>{score} of {outOf}</Typography>
      <Typography sx={{ color: 'text.secondary', mt: 1 }}>{verdict}</Typography>
      {marks}
      <Stack direction="row" spacing={1.5} useFlexGap sx={{ justifyContent: 'center', mt: 3, flexWrap: 'wrap', rowGap: 1 }}>
        <Button variant="contained" onClick={() => void sharer.share({ text: shareText() })}>
          {sharer.copied ? 'Copied' : sharer.canShareSheet ? 'Share result' : 'Copy result'}
        </Button>
        <Button variant="outlined" onClick={onAnother}>Another set</Button>
      </Stack>
      {tallyText && <Typography variant="body2" sx={{ color: 'text.secondary', mt: 3 }}>{tallyText}</Typography>}
      {offerToday && <Button sx={{ mt: 1 }} onClick={onToday}>Play today’s set</Button>}
    </Box>
  )
}
