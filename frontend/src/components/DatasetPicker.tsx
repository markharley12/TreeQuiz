import { Box, ButtonBase, Typography } from '@mui/material'
import { DATASETS } from '../engine/datasets'
import { shortTitle } from '../words'
import { ACCENT, CARD, FONT_DISPLAY, INK_MUTED, LINE } from '../theme'

interface Props {
  selected: string
  onPick: (id: string) => void
}

/** The trees there are to play, as cards: which one is a choice the front page
 *  should show at a glance rather than bury in the settings menu. */
export default function DatasetPicker({ selected, onPick }: Props) {
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
            <Typography sx={{ fontFamily: FONT_DISPLAY, fontWeight: 600, fontSize: '1.15rem', lineHeight: 1.2 }}>
              {shortTitle(manifest)}
            </Typography>
            <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5, fontSize: '0.8rem', lineHeight: 1.35 }}>
              {manifest.blurb}
            </Typography>
          </ButtonBase>
        )
      })}
    </Box>
  )
}
