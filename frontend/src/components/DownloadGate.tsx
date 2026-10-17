import { Alert, Box, Button, CircularProgress, Link, Stack, Typography } from '@mui/material'
import DatasetPicker from './DatasetPicker'
import Progress from './DownloadProgress'
import { cancel, download, refresh } from '../engine/downloads'
import { formatBytes } from '../engine/catalogue'
import { useTree } from '../useDownloads'
import { shortTitle } from '../words'
import { FONT_DISPLAY } from '../theme'

interface Props {
  dataset: string
  ready: boolean
  onPick: (id: string) => void
  onManage: () => void
}

/** The front page of a tree that is not on the device and will not download
 *  itself: a big one, which asks first and says how much, or one only the
 *  website has, which needs a connection. A link to such a tree lands here
 *  too, and plays once it is down. */
export default function DownloadGate({ dataset, ready, onPick, onManage }: Props) {
  const t = useTree(dataset)
  if (!t) return null
  const title = shortTitle(t.manifest)

  let panel: React.ReactNode
  if (!ready) {
    panel = <CircularProgress />
  } else if (t.progress) {
    panel = (
      <Box sx={{ width: '100%', maxWidth: 420 }}>
        <Typography sx={{ textAlign: 'center' }}>Downloading {title}…</Typography>
        <Progress p={t.progress} />
        <Box sx={{ textAlign: 'center', mt: 1 }}><Button onClick={() => cancel(t.id)}>Cancel</Button></Box>
      </Box>
    )
  } else if (t.offer) {
    panel = (
      <>
        <Typography sx={{ textAlign: 'center', maxWidth: 520 }}>
          {title} is a big tree: {formatBytes(t.offer.gzip)} to download, {formatBytes(t.offer.bytes)} on
          this device. It stays here, playable offline, until you delete it.
        </Typography>
        <Button variant="contained" size="large" onClick={() => void download(t.id).catch(() => {})}>
          Download {formatBytes(t.offer.gzip)}
        </Button>
      </>
    )
  } else {
    panel = (
      <>
        <Typography sx={{ textAlign: 'center', maxWidth: 520 }}>
          {title} comes from the TreeQuiz website, and this device has not downloaded it yet. It
          needs a connection.
        </Typography>
        <Button variant="outlined" onClick={() => void refresh()}>Try again</Button>
      </>
    )
  }

  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', p: { xs: 2, sm: 3 } }}>
      <Box sx={{ width: '100%', maxWidth: 760 }}>
        <Typography variant="h2" sx={{ fontSize: { xs: '2.6rem', sm: '3.4rem' }, textAlign: 'center', mb: 3 }}>TreeQuiz</Typography>
        <DatasetPicker selected={dataset} onPick={(id) => id !== dataset && onPick(id)} />
        <Stack spacing={2} sx={{ alignItems: 'center', mt: 3 }}>
          <Typography sx={{ fontFamily: FONT_DISPLAY, fontSize: '1.15rem' }}>{t.manifest.blurb}</Typography>
          {panel}
          {t.error && <Alert severity="error">{t.error}</Alert>}
          <Link component="button" variant="body2" onClick={onManage}>Manage trees</Link>
        </Stack>
      </Box>
    </Box>
  )
}
