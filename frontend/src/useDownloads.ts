import { useSyncExternalStore } from 'react'
import { downloads, subscribe, type Downloads, type TreeState } from './engine/downloads'

/** Which trees are on the device, and what fetching the rest costs; see
 *  engine/downloads.ts. Re-renders on every change, progress included. */
export function useDownloads(): Downloads {
  return useSyncExternalStore(subscribe, downloads)
}

export function useTree(id: string): TreeState | undefined {
  return useDownloads().trees.get(id)
}
