import { useState } from 'react'
import { Box, Slider, Typography } from '@mui/material'
import type { Sizes } from '../engine/size'
import { sizeText, sliderMarks, type Size } from '../sizes'
import { FONT_DISPLAY } from '../theme'

interface Props {
  sizes: Sizes
  size: Size
  /** "animals". */
  plural: string
  /** A size chosen: once let go, not at every mark passed on the way. */
  onChange: (size: Size) => void
}

/** How much of a sized tree to play, on the front page: logarithmic, and
 *  snapping to the tree's stops and to the whole tree. A size is a game of
 *  its own (sizes.ts), so letting go is a switch, as picking a tree is. */
export default function SizeSlider({ sizes, size, plural, onChange }: Props) {
  const marks = sliderMarks(sizes)
  const valueOf = (s: Size) => marks.find((m) => m.size === s)?.value ?? marks[0].value
  const sizeAt = (v: number) => marks.find((m) => m.value === v)?.size ?? sizes.default
  // Where the thumb is while it is dragged; the size played until let go.
  const [dragging, setDragging] = useState<Size | null>(null)
  const shown = dragging ?? size

  return (
    <Box sx={{ maxWidth: 520, mx: 'auto', mb: 2, px: { xs: 2.5, sm: 3 } }}>
      <Slider
        aria-label="How many to play with"
        value={valueOf(shown)}
        min={marks[0].value}
        max={marks[marks.length - 1].value}
        step={null}
        marks={marks.map(({ value, label }) => ({ value, label }))}
        getAriaValueText={(v) => sizeText(sizeAt(v))}
        valueLabelDisplay="off"
        onChange={(_, v) => setDragging(sizeAt(v as number))}
        onChangeCommitted={(_, v) => { setDragging(null); onChange(sizeAt(v as number)) }}
        sx={{ '& .MuiSlider-markLabel': { fontSize: '0.75rem' } }}
      />
      <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary', fontFamily: FONT_DISPLAY, fontStyle: 'italic' }}>
        {shown === 'all' ? `Every one of the ${plural}, however obscure.` : `The ${sizeText(shown)} best-known ${plural}.`}
        {shown !== sizes.default && ` Today’s is always from the ${sizeText(sizes.default)}.`}
      </Typography>
    </Box>
  )
}
