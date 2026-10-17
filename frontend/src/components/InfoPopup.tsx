import { useEffect, useState } from 'react'
import {
  Dialog, DialogTitle, DialogContent, DialogActions,
  Button, Chip, Typography, Box, CircularProgress, Link,
} from '@mui/material'
import { type Info } from '../api'
import { treeOf, useGame } from '../sizes'
import { loadInfo } from '../infoCache'
import { entryFor } from '../engine/datasets'
import { displayName } from '../names'
import { infoSource } from '../words'
import { IMAGE_MAT } from '../theme'

interface Props {
  names: string[]   // one or more node names (a compressed chain has several)
  onClose: () => void
}

interface Entry {
  name: string
  info: Info | null
}

const COLLAPSED_CHARS = 480

/** Shorten long text for the popup. Display-only — "Show more" gives it back.
 *
 *  Cutting at the first paragraph break is the main move (a Wikipedia intro is
 *  often five paragraphs), and a single overlong paragraph is then clamped at a
 *  sentence boundary. An abbreviation can fool that; it only costs a slightly
 *  early cut on a preview you can expand. */
function shorten(text: string): string {
  const firstPara = text.split('\n')[0]
  if (firstPara.length <= COLLAPSED_CHARS) return firstPara
  const window = firstPara.slice(0, COLLAPSED_CHARS)
  const sentence = window.lastIndexOf('. ')
  if (sentence > COLLAPSED_CHARS / 2) return window.slice(0, sentence + 1)
  const space = window.lastIndexOf(' ')
  return `${window.slice(0, space > 0 ? space : COLLAPSED_CHARS)}…`
}

function Description({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false)
  const short = shorten(text)
  const truncated = short.length < text.length
  // Paragraph breaks are newlines, which HTML would collapse into one wall of
  // text — so split rather than relying on the browser.
  const paragraphs = (expanded ? text.split('\n') : [short]).filter((p) => p.trim())

  return (
    <>
      {paragraphs.map((paragraph, i) => (
        <Typography key={i} variant="body2" sx={{ mb: i < paragraphs.length - 1 ? 1.25 : 0 }}>
          {paragraph}
        </Typography>
      ))}
      {truncated && (
        <Link
          component="button"
          type="button"
          variant="caption"
          underline="hover"
          onClick={() => setExpanded((e) => !e)}
          sx={{ display: 'block', mt: 1 }}
        >
          {expanded ? 'Show less' : 'Show more'}
        </Link>
      )}
    </>
  )
}

/** How many of a node's contents to list before "and N more". */
const ITEMS_SHOWN = 12

function Items({ items }: { items: string[] }) {
  const [all, setAll] = useState(false)
  const shown = all ? items : items.slice(0, ITEMS_SHOWN)
  return (
    <Box sx={{ mt: 1.5 }}>
      <Typography variant="caption" sx={{ color: 'text.secondary', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
        Includes
      </Typography>
      <Box component="ul" sx={{ m: 0, mt: 0.5, pl: 2.5 }}>
        {shown.map((item, i) => (
          <Typography component="li" variant="body2" key={i} sx={{ mb: 0.25 }}>{item}</Typography>
        ))}
      </Box>
      {items.length > ITEMS_SHOWN && (
        <Link component="button" type="button" variant="caption" underline="hover" onClick={() => setAll((a) => !a)}>
          {all ? 'Show fewer' : `and ${items.length - ITEMS_SHOWN} more`}
        </Link>
      )}
    </Box>
  )
}

export default function InfoPopup({ names, onClose }: Props) {
  const [entries, setEntries] = useState<Entry[]>([])
  const [loading, setLoading] = useState(true)
  const dataset = useGame()
  const manifest = entryFor(treeOf(dataset))?.manifest
  // The licence the popup text carries, for the notice under it. CC BY-SA and
  // BY-NC-SA both ask for it.
  const licensed = manifest ? infoSource(manifest) : undefined

  useEffect(() => {
    let cancelled = false
    // Clearing here is the point: the popup must not keep showing the previous
    // node's text while the next one loads.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setEntries([])
    Promise.all(names.map(async (name) => ({ name, info: await loadInfo(name, dataset) })))
      .then((results) => {
        if (!cancelled) {
          setEntries(results)
          setLoading(false)
        }
      })
    return () => { cancelled = true }
  }, [names, dataset])

  return (
    <Dialog open onClose={onClose} maxWidth="sm" fullWidth>
      {loading ? (
        <DialogContent sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
          <CircularProgress />
        </DialogContent>
      ) : (
        <>
          {entries.map(({ name, info }, i) => {
            const hasText = Boolean(info?.description || info?.items?.length || info?.image_url)
            return (
              <Box key={name} sx={i > 0 ? { borderTop: 1, borderColor: 'divider' } : {}}>
                {/* Led by the label — you clicked "lion", so being answered by
                    "Panthera leo" reads as the wrong article. The name still
                    shows underneath when it differs. */}
                <DialogTitle sx={{ pb: 0.5 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Box component="span">{displayName(info?.label || name)}</Box>
                    {info?.rank && <Chip label={info.rank} size="small" />}
                  </Box>
                  {info && info.label !== name && !manifest?.hide_names && (
                    <Typography variant="body2" sx={{ fontStyle: 'italic', color: 'text.secondary' }}>
                      {name}
                    </Typography>
                  )}
                  {info?.subtitle && (
                    <Typography variant="body2" sx={{ color: 'text.secondary' }}>
                      {info.subtitle}
                    </Typography>
                  )}
                </DialogTitle>

                <DialogContent>
                  {hasText ? (
                    <>
                      {info?.image_url && (
                        /* Letterboxed rather than cropped, on a fixed aspect so
                           the popup does not jump when the image loads. */
                        <Box sx={{ aspectRatio: '16 / 9', bgcolor: IMAGE_MAT, border: 1, borderColor: 'divider', borderRadius: 1, overflow: 'hidden', mb: 1.5 }}>
                          <Box
                            component="img"
                            src={info.image_url}
                            alt={info.label}
                            sx={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }}
                          />
                        </Box>
                      )}
                      {info?.description && <Description text={info.description} />}
                      {info?.items && info.items.length > 0 && <Items items={info.items} />}
                      {/* The notice the text's licence asks for, now that it is
                        * served to anyone from a public website. Not under a
                        * picture alone: a board drawn here is nobody's text. */}
                      {(info?.url || ((info?.description || info?.items?.length) && manifest?.info_source)) && (
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1.5 }}>
                          {info?.url ? (
                            <Link href={info.url} target="_blank" rel="noopener">
                              {info.url_title || `From ${manifest?.info_source ?? 'the source'}`}
                            </Link>
                          ) : `From ${manifest?.info_source}`}
                          {licensed?.licence && <>
                            {' · '}
                            {licensed.licence_url
                              ? <Link href={licensed.licence_url} target="_blank" rel="noopener">{licensed.licence}</Link>
                              : licensed.licence}
                          </>}
                        </Typography>
                      )}
                    </>
                  ) : (
                    <Typography variant="body2" color="text.secondary">
                      No information available.
                    </Typography>
                  )}
                </DialogContent>
              </Box>
            )
          })}

          <DialogActions>
            <Button onClick={onClose}>Close</Button>
          </DialogActions>
        </>
      )}
    </Dialog>
  )
}
