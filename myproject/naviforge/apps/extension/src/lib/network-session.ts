import {
  attachNetwork,
  detachNetwork,
  ensureNetworkListeners,
  segmentNetworkTab,
} from './network-recorder.js'

/** Toolkit tabs with persistent CDP observation (survives agent run end). */
const boundToolkitTabs = new Set<number>()

export function isToolkitTabBound(tabId: number): boolean {
  return boundToolkitTabs.has(tabId)
}

/** B1: attach when user selects / adopts a toolkit tab (before agent run). */
export async function bindToolkitTabNetwork(tabId: number): Promise<{ ok: boolean; error?: string }> {
  ensureNetworkListeners()
  boundToolkitTabs.add(tabId)
  try {
    const tab = await chrome.tabs.get(tabId)
    if (tab.url) segmentNetworkTab(tabId, tab.url)
  } catch {
    /* tab may be gone */
  }
  const r = await attachNetwork(tabId, { captureBodies: true })
  return r.attached ? { ok: true } : { ok: false, error: r.error }
}

export function unbindToolkitTabNetwork(tabId: number): void {
  boundToolkitTabs.delete(tabId)
}

/** End of agent run: detach only when tab is not bound to toolkit session. */
export async function releaseRunNetwork(tabId: number): Promise<void> {
  if (boundToolkitTabs.has(tabId)) return
  await detachNetwork(tabId)
}

/** C / F1: navigation boundary — archive prior page network slice. */
export function onToolkitTabNavigated(tabId: number, url: string): void {
  if (!boundToolkitTabs.has(tabId)) return
  if (!url || url.startsWith('chrome://') || url.startsWith('chrome-extension://')) return
  segmentNetworkTab(tabId, url)
}

let sessionListeners = false

export function ensureTabNetworkSessionListeners(): void {
  if (sessionListeners) return
  sessionListeners = true
  ensureNetworkListeners()

  // F1: main-frame commit is a sharper boundary than tabs.onUpdated.url
  chrome.webNavigation.onCommitted.addListener((details) => {
    if (details.frameId !== 0) return
    onToolkitTabNavigated(details.tabId, details.url)
  })

  chrome.tabs.onRemoved.addListener((tabId) => {
    boundToolkitTabs.delete(tabId)
  })
}
