import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from '@mui/material'
import { BUCKETS, bucketOf, computeStats, readDailies, score, scoreText, shareText, squares } from '../results'
import { utcToday } from '../engine/seed'
import { shareBase, shareLink } from '../shareLink'
import { useSharer } from '../sharer'
import { ACCENT, FONT_DISPLAY, LINE } from '../theme'
import { useCloseOnBack } from '../backButton'

interface Props {
  open: boolean
  onClose: () => void
  dataset: string
  /** The tree's short title, for the heading. */
  title: string
}

/** One tree's dailies on this device: today's result, ready to share; how
 *  many played and won, the streak, and how many guesses the wins took. Read
 *  on open, so it is never stale. */
export default function StatsDialog({ open, onClose, dataset, title }: Props) {
  const { share, copied, canShareSheet } = useSharer()
  useCloseOnBack(open, onClose)
  if (!open) return null
  const today = utcToday()
  const records = readDailies(dataset)
  const mine = records[today]
  const s = computeStats(records, today)
  const todays = records[today]?.won ? bucketOf(score(records[today])) : -1
  const tallest = Math.max(1, ...s.histogram)

  const figures: [string, string][] = [
    ['Played', String(s.played)],
    ['Won', s.played ? `${Math.round((100 * s.won) / s.played)}%` : '–'],
    ['Streak', String(s.streak)],
    ['Best', String(s.bestStreak)],
  ]

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs">
      <DialogTitle sx={{ fontFamily: FONT_DISPLAY }}>{title}: your dailies</DialogTitle>
      <DialogContent>
        {mine && (
          <Box sx={{ mb: 2, pb: 2, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="body2" sx={{ color: 'text.secondary' }}>
              Today: {scoreText(mine.guesses.length, mine.hints, mine.hintPoints, mine.won)}
            </Typography>
            <Stack direction="row" spacing={2} sx={{ alignItems: 'center', justifyContent: 'space-between' }}>
              <Typography component="pre" aria-label="Today's result" sx={{ m: 0, fontSize: '1.05rem', lineHeight: 1.3, fontFamily: 'inherit', whiteSpace: 'pre' }}>
                {squares(mine.warmths)}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                sx={{ flexShrink: 0 }}
                onClick={() => share({ text: shareText({
                  title, daily: true, day: today, warmths: mine.warmths, hints: mine.hints,
                  hintPoints: mine.hintPoints, won: mine.won, link: shareLink(shareBase(window.location.href), dataset, mine.seed),
                }) })}
              >
                {copied ? 'Copied' : canShareSheet ? 'Share' : 'Copy result'}
              </Button>
            </Stack>
          </Box>
        )}
        <Stack direction="row" sx={{ justifyContent: 'space-around', mb: 2 }}>
          {figures.map(([label, value]) => (
            <Box key={label} sx={{ textAlign: 'center' }}>
              <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '1.9rem', lineHeight: 1.1 }}>{value}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
                {label}
              </Typography>
            </Box>
          ))}
        </Stack>
        {s.won === 0 ? (
          <Typography variant="body2" sx={{ color: 'text.secondary', textAlign: 'center' }}>
            {s.played === 0 ? 'No dailies on this tree yet. Every tree has its own each day.' : 'No wins yet to chart.'}
          </Typography>
        ) : (
          <>
            <Typography variant="body2" sx={{ color: 'text.secondary', mb: 1 }}>
              Guesses per win{s.average !== null && ` — ${s.average.toFixed(1)} on average`}, hints counted at their cost
            </Typography>
            <Box role="list" aria-label="Guesses per win">
              {BUCKETS.map((b, i) => (
                <Stack key={b.label} role="listitem" direction="row" spacing={1} sx={{ alignItems: 'center', mb: 0.5 }}>
                  <Typography variant="body2" sx={{ width: 44, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{b.label}</Typography>
                  <Box sx={{ flex: 1 }}>
                    <Box
                      sx={{
                        width: `${Math.max(6, (100 * s.histogram[i]) / tallest)}%`, minWidth: 22,
                        bgcolor: i === todays ? ACCENT : LINE, color: i === todays ? '#fff' : 'text.primary',
                        borderRadius: 1, px: 0.75, py: 0.25, textAlign: 'right', fontSize: '0.8rem', fontWeight: 600,
                        boxSizing: 'border-box',
                      }}
                    >
                      {s.histogram[i]}
                    </Box>
                  </Box>
                </Stack>
              ))}
            </Box>
          </>
        )}
        <Typography variant="caption" sx={{ display: 'block', mt: 2, color: 'text.secondary' }}>
          Kept on this device only. A daily counts the first time it is finished; a
          give-up or a missed day ends a streak.
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} autoFocus>Close</Button>
      </DialogActions>
    </Dialog>
  )
}
