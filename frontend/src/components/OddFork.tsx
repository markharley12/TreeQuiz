import type { ReactNode } from 'react'
import { Box, ButtonBase, Typography } from '@mui/material'
import { makeColorScale, makeTintScale } from '../colors'
import { displayName } from '../names'
import type { Box as RevealBox, Reveal } from '../oddReveal'
import { useSettings } from '../settings'
import { CARD, FONT_DISPLAY, INK, INK_MUTED, LINE, TREE_LINK } from '../theme'

const DROP = 14

/** A node and, below it, its children joined by an elbow: the org-chart
 *  drawing, in boxes and borders so long names wrap rather than overflow. */
function Branch({ head, kids, weights }: { head: ReactNode; kids: ReactNode[]; weights: number[] }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
      {head}
      <Box sx={{ width: '1px', height: DROP, bgcolor: TREE_LINK }} />
      <Box sx={{ display: 'flex', width: '100%', alignItems: 'flex-start' }}>
        {kids.map((kid, i) => (
          <Box
            key={i}
            sx={{
              flex: weights[i], minWidth: 0, position: 'relative', pt: `${DROP}px`, px: 0.5,
              display: 'flex', flexDirection: 'column', alignItems: 'center',
              '&::before': {
                content: '""', position: 'absolute', top: 0, borderTop: `1px solid ${TREE_LINK}`,
                left: i === 0 ? '50%' : 0, right: i === kids.length - 1 ? '50%' : 0,
              },
              '&::after': { content: '""', position: 'absolute', top: 0, left: '50%', height: DROP, borderLeft: `1px solid ${TREE_LINK}` },
            }}
          >
            {kid}
          </Box>
        ))}
      </Box>
    </Box>
  )
}

export type LeafMark = 'odd' | 'wrong' | null

interface Props {
  reveal: Reveal
  /** How each leaf is marked, by its name. */
  marks: Map<string, LeafMark>
  onOpen: (name: string) => void
}

/** Where the three meet, the fork to the pair's group and the odd one, and
 *  the pair. Groups carry their warmth as a spine, as in the game tree; any
 *  node opens its popup. */
export default function OddFork({ reveal, marks, onOpen }: Props) {
  const { colorScheme } = useSettings()
  const colorFor = makeColorScale(colorScheme)
  const tintFor = makeTintScale(colorScheme)

  const node = (b: RevealBox, leaf: boolean) => {
    const mark = leaf ? marks.get(b.name) ?? null : null
    const color = colorFor(b.warmth)
    return (
      <ButtonBase
        onClick={() => onOpen(b.name)}
        aria-label={`${displayName(b.text)}${mark === 'odd' ? ', the odd one out' : mark === 'wrong' ? ', your pick' : ''}`}
        sx={{
          display: 'block', textAlign: 'left', maxWidth: 240, width: leaf ? '100%' : 'auto', minWidth: 0,
          px: 1.25, py: 0.75, borderRadius: 1.25, fontFamily: FONT_DISPLAY,
          ...(leaf
            ? { bgcolor: CARD, border: '1px solid', color: INK,
                borderColor: mark === 'odd' ? 'success.main' : mark === 'wrong' ? 'error.main' : LINE,
                borderWidth: mark ? 2 : 1 }
            : { bgcolor: tintFor(b.warmth), color: INK, border: `1px solid ${LINE}`, borderLeft: `5px solid ${color}` }),
          '&:hover': { borderColor: leaf ? INK : color },
        }}
      >
        {b.above && (
          <Typography component="span" sx={{ display: 'block', fontSize: '0.72rem', color: INK_MUTED, lineHeight: 1.25, fontFamily: 'inherit' }}>
            {b.above}
          </Typography>
        )}
        <Typography component="span" sx={{ display: 'block', fontSize: '0.92rem', fontWeight: leaf ? 700 : 600, lineHeight: 1.25, fontFamily: 'inherit', overflowWrap: 'anywhere' }}>
          {displayName(b.text)}
        </Typography>
        {mark && (
          <Typography component="span" sx={{ display: 'block', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', fontFamily: 'inherit', color: mark === 'odd' ? 'success.dark' : 'error.dark' }}>
            {mark === 'odd' ? 'Odd one out' : 'Your pick'}
          </Typography>
        )}
      </ButtonBase>
    )
  }

  return (
    <Branch
      head={node(reveal.shared, false)}
      weights={[2, 1]}
      kids={[
        <Branch key="pair" head={node(reveal.group, false)} weights={[1, 1]} kids={reveal.pair.map((b) => <Box key={b.name} sx={{ width: '100%' }}>{node(b, true)}</Box>)} />,
        <Box key="odd" sx={{ width: '100%' }}>{node(reveal.odd, true)}</Box>,
      ]}
    />
  )
}
