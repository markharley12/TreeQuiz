import { Fragment } from 'react'
import { Box, ButtonBase, Typography } from '@mui/material'
import { makeColorScale, makeTintScale } from '../colors'
import { displayName } from '../names'
import type { Box as RevealBox } from '../oddReveal'
import { ordinal, type Ladder } from '../lineupReveal'
import { useSettings } from '../settings'
import { ACCENT, CARD, FONT_DISPLAY, INK, INK_MUTED, LINE, TREE_LINK } from '../theme'

const GAP = 14

interface Props {
  ladder: Ladder
  /** Where the player put each of the four, by label: 0 is first. */
  placed: Map<string, number>
  onOpen: (name: string) => void
}

/** The target's lineage as a spine, a rung where each of the four meets it,
 *  each hanging off its rung, and the target at the foot: reading down is
 *  reading nearer. Every box opens its popup. */
export default function LineUpLadder({ ladder, placed, onOpen }: Props) {
  const { colorScheme } = useSettings()
  const colorFor = makeColorScale(colorScheme)
  const tintFor = makeTintScale(colorScheme)

  const box = (b: RevealBox, kind: 'meet' | 'option' | 'target', place?: number) => {
    const yours = kind === 'option' ? placed.get(b.text) : undefined
    const right = yours !== undefined && yours === place
    const color = colorFor(b.warmth)
    const label = kind === 'option' && place !== undefined
      ? `${displayName(b.text)}, ${ordinal(place)}${right ? '' : `, you put it ${yours === undefined ? 'nowhere' : ordinal(yours)}`}`
      : displayName(b.text)
    return (
      <ButtonBase
        onClick={() => onOpen(b.name)}
        aria-label={label}
        sx={{
          display: 'block', textAlign: 'left', width: '100%', minWidth: 0, position: 'relative', zIndex: 1,
          px: 1.25, py: 0.75, borderRadius: 1.25, fontFamily: FONT_DISPLAY, color: INK,
          ...(kind === 'meet'
            ? { bgcolor: tintFor(b.warmth), border: `1px solid ${LINE}`, borderLeft: `5px solid ${color}` }
            : kind === 'target'
              ? { bgcolor: CARD, border: `2px solid ${ACCENT}` }
              : { bgcolor: CARD, border: '2px solid', borderColor: right ? 'success.main' : 'error.main' }),
          '&:hover': { borderColor: kind === 'meet' ? color : INK },
        }}
      >
        {b.above && (
          <Typography component="span" sx={{ display: 'block', fontSize: '0.72rem', color: INK_MUTED, lineHeight: 1.25, fontFamily: 'inherit' }}>
            {b.above}
          </Typography>
        )}
        <Typography component="span" sx={{ display: 'block', fontSize: '0.92rem', fontWeight: kind === 'meet' ? 600 : 700, lineHeight: 1.25, fontFamily: 'inherit', overflowWrap: 'anywhere' }}>
          {displayName(b.text)}
        </Typography>
        {kind !== 'meet' && (
          <Typography component="span" sx={{
            display: 'block', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', fontFamily: 'inherit',
            color: kind === 'target' ? ACCENT : right ? 'success.dark' : 'error.dark',
          }}>
            {kind === 'target' ? 'Target' : right ? `${ordinal(place!)} ✓` : `${ordinal(place!)} · you said ${yours === undefined ? '—' : ordinal(yours)}`}
          </Typography>
        )}
      </ButtonBase>
    )
  }

  // The spine runs down the middle of the left column, behind the boxes, from
  // the top rung to the target; a rung's branch runs right to its leaf.
  const spine = (top: string, bottom: string) => ({
    position: 'relative', display: 'flex', alignItems: 'center',
    '&::before': { content: '""', position: 'absolute', left: '50%', top, bottom, borderLeft: `1px solid ${TREE_LINK}` },
  }) as const

  return (
    <Box sx={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 20px minmax(0, 1fr)', rowGap: `${GAP}px` }}>
      {ladder.rungs.map((r, i) => (
        <Fragment key={r.meet.name}>
          <Box sx={spine(i === 0 ? '50%' : `-${GAP / 2}px`, `-${GAP / 2}px`)}>{box(r.meet, 'meet')}</Box>
          <Box sx={{ display: 'flex', alignItems: 'center' }}><Box sx={{ width: '100%', borderTop: `1px solid ${TREE_LINK}` }} /></Box>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>{box(r.option, 'option', r.place)}</Box>
        </Fragment>
      ))}
      <Box sx={spine(`-${GAP / 2}px`, '50%')}>{box(ladder.target, 'target')}</Box>
    </Box>
  )
}
