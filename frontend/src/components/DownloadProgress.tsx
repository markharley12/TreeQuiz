import { Box, LinearProgress, Typography } from '@mui/material'
import { formatBytes } from '../engine/catalogue'

/** A download's bar, and how far it has got. */
export default function Progress({ p }: { p: { done: number; total: number } }) {
  const pct = p.total ? (100 * p.done) / p.total : 0
  return (
    <Box sx={{ mt: 0.75 }}>
      <LinearProgress variant={p.total ? 'determinate' : 'indeterminate'} value={pct} aria-label="Download progress" />
      <Typography variant="caption" sx={{ color: 'text.secondary' }}>
        {formatBytes(p.done)} of {formatBytes(p.total)}
      </Typography>
    </Box>
  )
}
