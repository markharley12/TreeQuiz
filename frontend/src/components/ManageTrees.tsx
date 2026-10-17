import { useEffect, useState } from 'react'
import {
  Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle, FormControlLabel,
  Stack, Typography,
} from '@mui/material'
import Progress from './DownloadProgress'
import { DATASETS, forgetProgress } from '../engine/datasets'
import { cancel, download, refresh, remove, type TreeState } from '../engine/downloads'
import { formatBytes } from '../engine/catalogue'
import { useDownloads } from '../useDownloads'
import { shortTitle } from '../words'
import { FONT_DISPLAY } from '../theme'

interface Props {
  open: boolean
  onClose: () => void
  /** A tree's saved round and stats were forgotten. */
  onForgot: (id: string) => void
}

/** Which trees are on this device and what each takes, with Delete — and
 *  Download, Update and Finish for the rest. */
export default function ManageTrees({ open, onClose, onForgot }: Props) {
  const { trees, lasting } = useDownloads()
  const [deleting, setDeleting] = useState<TreeState | null>(null)
  const [usage, setUsage] = useState<{ usage?: number; quota?: number } | null>(null)

  const held = [...trees.values()].reduce((sum, t) => sum + (t.copy && !t.bundled ? t.copy.bytes : 0), 0)

  // Asked again here: a page left open for days learns of new versions.
  useEffect(() => {
    if (open) void refresh()
  }, [open])
  useEffect(() => {
    if (open) navigator.storage?.estimate?.().then(setUsage, () => {})
  }, [open, held])

  if (!open) return null

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm">
      <DialogTitle sx={{ fontFamily: FONT_DISPLAY }}>Trees on this device</DialogTitle>
      <DialogContent>
        <Stack divider={<Box sx={{ borderTop: 1, borderColor: 'divider' }} />} spacing={1.25}>
          {DATASETS.map(({ id }) => {
            const t = trees.get(id)
            return t && <Row key={id} t={t} onDelete={() => setDeleting(t)} />
          })}
        </Stack>
        <Typography variant="body2" sx={{ mt: 2.5, color: 'text.secondary' }}>
          Downloads take {formatBytes(held)}.
          {usage?.usage !== undefined && usage.quota !== undefined && (
            <> All of TreeQuiz, the app itself included, takes {formatBytes(usage.usage)} of the {formatBytes(usage.quota)} this browser allows it.</>
          )}
          {!lasting && <> This browser is not keeping downloads, so they last only until the page is closed.</>}
        </Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Done</Button>
      </DialogActions>
      {deleting && (
        <ConfirmDelete
          t={deleting}
          onCancel={() => setDeleting(null)}
          onDelete={(forget) => {
            const id = deleting.id
            setDeleting(null)
            void remove(id).then(() => {
              if (!forget) return
              forgetProgress(id)
              onForgot(id)
            })
          }}
        />
      )}
    </Dialog>
  )
}

function Row({ t, onDelete }: { t: TreeState; onDelete: () => void }) {
  const title = shortTitle(t.manifest)
  let status: string
  if (t.bundled) status = `Part of the app · ${formatBytes(t.copy?.bytes ?? 0)}`
  else if (t.copy) status = `${formatBytes(t.copy.bytes)} on this device${t.copy.missing ? ' · some text still to fetch' : ''}`
  else if (t.offer) status = `Not downloaded · ${formatBytes(t.offer.bytes)}`
  else status = 'Not downloaded · needs a connection to the website'

  return (
    <Box>
      <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontWeight: 600 }}>{title}</Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>{status}</Typography>
        </Box>
        {t.progress ? (
          <Button size="small" onClick={() => cancel(t.id)}>Cancel</Button>
        ) : (
          <>
            {t.update && t.offer && (
              <Button size="small" variant="outlined" onClick={() => void download(t.id).catch(() => {})}>
                Update ({formatBytes(t.offer.gzip)})
              </Button>
            )}
            {t.copy && !t.update && t.copy.missing > 0 && (
              <Button size="small" variant="outlined" onClick={() => void download(t.id).catch(() => {})}>Finish</Button>
            )}
            {!t.copy && t.offer && (
              <Button size="small" variant="outlined" onClick={() => void download(t.id).catch(() => {})}>
                Download ({formatBytes(t.offer.gzip)})
              </Button>
            )}
            {t.copy && !t.bundled && (
              <Button size="small" color="error" onClick={onDelete}>Delete</Button>
            )}
          </>
        )}
      </Stack>
      {t.progress && <Progress p={t.progress} />}
      {t.error && <Typography variant="body2" sx={{ color: 'error.main', mt: 0.5 }}>{t.error}</Typography>}
    </Box>
  )
}

function ConfirmDelete({ t, onCancel, onDelete }: { t: TreeState; onCancel: () => void; onDelete: (forget: boolean) => void }) {
  const [forget, setForget] = useState(false)
  const title = shortTitle(t.manifest)
  return (
    <Dialog open onClose={onCancel} maxWidth="xs">
      <DialogTitle sx={{ fontFamily: FONT_DISPLAY }}>Delete {title}?</DialogTitle>
      <DialogContent>
        <Typography variant="body2">
          Frees {formatBytes(t.copy?.bytes ?? 0)}.
          {t.big ? ' Playing it again means downloading it again.' : ' It downloads again the next time you open it.'}
        </Typography>
        <FormControlLabel
          sx={{ mt: 1 }}
          control={<Checkbox checked={forget} onChange={(e) => setForget(e.target.checked)} />}
          label={`Also forget my saved round and stats on ${title}`}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>Keep it</Button>
        <Button color="error" onClick={() => onDelete(forget)}>Delete</Button>
      </DialogActions>
    </Dialog>
  )
}
