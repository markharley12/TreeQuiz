/**
 * What Android's back button does in the native app.
 *
 * With no listener, Capacitor closes the app from any screen, because the app
 * keeps no browser history to go back through. So back closes whatever was
 * opened most recently — a popup, a confirmation, the settings menu, a game
 * (whose closing is going Home, which keeps its round) — and with nothing
 * open, on the front page, it minimises the app.
 *
 * (TaxoQuiz's minimised from inside a round too: its way home cleared the
 * saved session, so back would have thrown away a daily that cannot be
 * replayed. TreeQuiz's Home keeps every round, so back can go there.)
 *
 * Overlays register themselves through `useCloseOnBack` rather than being listed
 * here, so a new dialog only has to call the hook to behave — and one that
 * does not is skipped by back, which closes what is under it instead.
 */
import { useEffect, useRef } from 'react'
import { Capacitor } from '@capacitor/core'
import { App } from '@capacitor/app'

type Entry = { close: () => void }

/** Open overlays, oldest first. Module-level because overlays live in unrelated
 *  parts of the component tree, and one back press has to reach the newest. */
const open: Entry[] = []

/** Register an open overlay. Returns the function that unregisters it, which is
 *  safe to call after a back press has already removed it. */
export function pushCloser(close: () => void): () => void {
  const entry = { close }
  open.push(entry)
  return () => {
    const i = open.lastIndexOf(entry)
    if (i !== -1) open.splice(i, 1)
  }
}

/** One back press: close the newest overlay, or `leave` when none is open. */
export function handleBack(leave: () => void): void {
  const newest = open.pop()
  if (newest) newest.close()
  else leave()
}

/** Close this overlay on back while `isOpen`. Always calls the latest `close`,
 *  so an inline arrow function does not re-register on every render — which
 *  would move the overlay to the top of the stack each time it re-rendered. */
export function useCloseOnBack(isOpen: boolean, close: () => void): void {
  const latest = useRef(close)
  useEffect(() => {
    latest.current = close
  })
  useEffect(() => {
    if (!isOpen) return
    return pushCloser(() => latest.current())
  }, [isOpen])
}

/** Listen for the hardware back button. Does nothing outside the native app: in
 *  a browser, back belongs to the browser. */
export function installBackButton(): void {
  if (!Capacitor.isNativePlatform()) return
  void App.addListener('backButton', () => {
    handleBack(() => void App.minimizeApp())
  })
}
