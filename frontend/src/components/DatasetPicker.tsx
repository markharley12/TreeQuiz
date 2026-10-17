import { Box, ButtonBase, Typography } from '@mui/material'
import { DATASETS } from '../engine/datasets'
import { utcToday } from '../engine/seed'
import { readDailies, score } from '../results'
import { shortTitle } from '../words'
import { chosenGame } from '../sizes'
import { formatBytes } from '../engine/catalogue'
import type { TreeState } from '../engine/downloads'
import { useDownloads } from '../useDownloads'
import { ACCENT, CARD, FONT_DISPLAY, INK_MUTED, LINE } from '../theme'

interface Props {
  selected: string
  onPick: (id: string) => void
}

/** Where a tree stands on this device, for its card: every tree is listed,
 *  downloaded or not, with what it takes. */
function deviceNote(t: TreeState | undefined): string {
  if (!t || t.bundled) return ''
  if (t.progress) return `Downloading… ${t.progress.total ? Math.floor((100 * t.progress.done) / t.progress.total) : 0}%`
  if (t.copy && t.update && t.big) return `On this device · update ${formatBytes(t.offer!.gzip)}`
  if (t.copy) return `On this device · ${formatBytes(t.copy.bytes)}`
  if (t.offer) return `${t.big ? 'Download first' : 'Downloads on opening'} · ${formatBytes(t.offer.bytes)}`
  return 'Needs a connection'
}

/** The trees there are to play, as cards: which one is a choice the front page
 *  should show at a glance rather than bury in the settings menu. */
export default function DatasetPicker({ selected, onPick }: Props) {
  const today = utcToday()
  const { ready, trees } = useDownloads()
  // At most four across, and rows as even as that allows: five trees went four
  // and a stray one, and read better as three and two.
  const rows = Math.ceil(DATASETS.length / 4)
  const across = Math.ceil(DATASETS.length / rows)
  return (
    <Box
      role="radiogroup"
      aria-label="Tree"
      sx={{
        display: 'grid', gap: 1.25,
        gridTemplateColumns: { xs: '1fr 1fr', sm: `repeat(${across}, 1fr)` },
      }}
    >
      {DATASETS.map(({ id, manifest }) => {
        const on = id === selected
        // Today's daily on this tree, done: a tick and its score, so the front
        // page shows which trees are still to play today. A sized tree's is
        // the one at the size it is played at.
        const done = readDailies(chosenGame(id))[today]
        return (
          <ButtonBase
            key={id}
            role="radio"
            aria-checked={on}
            onClick={() => onPick(id)}
            sx={{
              display: 'block', textAlign: 'left', p: 1.5, borderRadius: 2,
              bgcolor: CARD, border: '1px solid', borderColor: on ? ACCENT : LINE,
              boxShadow: on ? `0 0 0 1px ${ACCENT}` : '0 1px 2px rgba(44,38,32,0.08)',
              transition: 'border-color 120ms, box-shadow 120ms',
              '&:hover': { borderColor: on ? ACCENT : INK_MUTED },
            }}
          >
            <Typography sx={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: '1.15rem', lineHeight: 1.2, display: 'flex', alignItems: 'baseline', gap: 1 }}>
              {shortTitle(manifest)}
              {done && (
                <Box
                  component="span"
                  aria-label={done.won ? `Today's done in ${score(done)}` : 'Today\'s done, given up'}
                  sx={{ ml: 'auto', fontFamily: 'inherit', fontSize: '0.8rem', fontWeight: 600, color: done.won ? 'success.dark' : 'text.secondary', whiteSpace: 'nowrap' }}
                >
                  ✓{done.won ? ` ${score(done)}` : ''}
                </Box>
              )}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, fontSize: '0.8rem', lineHeight: 1.35 }}>
              {manifest.blurb}
            </Typography>
            {ready && deviceNote(trees.get(id)) && (
              <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', mt: 0.5, fontSize: '0.7rem', opacity: 0.85 }}>
                {deviceNote(trees.get(id))}
              </Typography>
            )}
          </ButtonBase>
        )
      })}
    </Box>
  )
}
