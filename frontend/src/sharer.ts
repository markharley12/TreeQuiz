import { useRef, useState } from 'react'
import { useCoarsePointer } from './media'

/** Sending something to someone: on a phone the share sheet, which is how a
 *  phone sends anything; elsewhere the clipboard, since a desktop share sheet
 *  is patchy. `copied` is true for a moment after a copy, for the button to
 *  say so. */
export function useSharer() {
  const canShareSheet = useCoarsePointer() && typeof navigator.share === 'function'
  const [copied, setCopied] = useState(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  async function share(data: { url?: string; text?: string }) {
    if (canShareSheet) {
      try {
        await navigator.share(data)
      } catch {
        // Dismissed, most likely. Nothing to undo.
      }
      return
    }
    try {
      await navigator.clipboard.writeText(data.text ?? data.url ?? '')
    } catch {
      return   // clipboard is blocked outside a secure context
    }
    setCopied(true)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => setCopied(false), 1500)
  }

  return { share, copied, canShareSheet }
}
