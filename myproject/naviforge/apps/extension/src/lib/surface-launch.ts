import { STORAGE } from './settings'
import { pinCurrentWebTab, resolveToolkitTab, setPinnedToolkitTabId } from './toolkit-actions'
import { showToolkitPaletteOnTab } from './toolkit-palette-open'

const SIDE_PANEL_PATH = 'sidepanel.html'

export const SIDE_PANEL_ENTRY = SIDE_PANEL_PATH

/** Pre-register side panel for a tab so `open()` can run synchronously on user gesture. */
export function registerSidePanelForTab(tabId: number): void {
  void chrome.sidePanel
    .setOptions({ tabId, path: SIDE_PANEL_PATH, enabled: true })
    .catch(() => {})
}

/** ponytail: MV3 `open()` returns a Promise; attach `.catch` so gesture rejections don't spam the console. */
function invokeSidePanelOpen(
  options: chrome.sidePanel.OpenOptions
): { ok: true } | { ok: false; error: string } {
  try {
    const maybePromise = chrome.sidePanel.open(options)
    if (
      maybePromise != null &&
      typeof (maybePromise as Promise<void>).then === 'function'
    ) {
      void (maybePromise as Promise<void>).catch(() => {})
    }
    return { ok: true }
  } catch (error) {
    const message =
      error instanceof Error ? error.message : 'side panel open failed'
    return { ok: false, error: message }
  }
}

/**
 * Open side panel while user-gesture is still active — no await before `open()`.
 * Call from click handlers / synchronous `onMessage` branches.
 */
export function openSidePanelWithGesture(
  tabId: number,
  windowId?: number
): { ok: true } | { ok: false; error: string } {
  registerSidePanelForTab(tabId)
  const openOpts: chrome.sidePanel.OpenOptions = { tabId }
  if (windowId != null) openOpts.windowId = windowId
  const byTab = invokeSidePanelOpen(openOpts)
  if (byTab.ok) return byTab
  if (windowId == null) return byTab
  return invokeSidePanelOpen({ windowId })
}

/** Screenshot studio (extension page): prefer windowId so side panel opens in current window. */
export function openSidePanelForStudioAttach(
  tabId: number,
  windowId?: number
): { ok: true } | { ok: false; error: string } {
  registerSidePanelForTab(tabId)
  if (windowId != null) {
    const both = invokeSidePanelOpen({ windowId, tabId })
    if (both.ok) return both
    const windowOnly = invokeSidePanelOpen({ windowId })
    if (windowOnly.ok) return windowOnly
  }
  return invokeSidePanelOpen({ tabId, windowId })
}

/** Popup click — query tab in callback, then open before gesture expires. */
export function openSidePanelFromPopupClick(): void {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0]
    if (tab?.id == null) return
    openSidePanelWithGesture(tab.id, tab.windowId)
  })
}

/** Enable + open Chrome side panel (Agent mode) for a specific tab. */
export async function openSidePanelForTab(
  tab: chrome.tabs.Tab
): Promise<{ ok: true } | { ok: false; error: string }> {
  const tabId = tab.id
  const windowId = tab.windowId
  if (tabId == null || windowId == null) {
    return { ok: false, error: 'missing tab' }
  }
  try {
    await chrome.sidePanel.setOptions({
      tabId,
      path: SIDE_PANEL_PATH,
      enabled: true,
    })
    await chrome.sidePanel.open({ tabId })
    return { ok: true }
  } catch (first) {
    try {
      await chrome.sidePanel.setOptions({ path: SIDE_PANEL_PATH, enabled: true })
      await chrome.sidePanel.open({ windowId })
      return { ok: true }
    } catch (second) {
      const message =
        second instanceof Error
          ? second.message
          : first instanceof Error
            ? first.message
            : 'side panel open failed'
      return { ok: false, error: message }
    }
  }
}

export async function ensureSidePanelRegistered(): Promise<void> {
  try {
    await chrome.sidePanel.setOptions({ path: SIDE_PANEL_PATH, enabled: true })
  } catch {
    /* older Chrome */
  }
}

export const TOOLKIT_OPEN_PALETTE = 'TOOLKIT_OPEN_PALETTE'

/** ⌥N：在当前网页打开可搜索的快捷工具浮层（非扩展小弹窗）。 */
export async function openPageToolList(): Promise<{ ok: boolean; error?: string }> {
  const tab = await resolveToolkitTab()
  if (!tab?.id) {
    return { ok: false, error: '请先打开一个普通网页' }
  }
  return showToolkitPaletteOnTab(tab.id)
}

export async function openWorkspaceTab(tabId?: number): Promise<void> {
  if (tabId != null) await setPinnedToolkitTabId(tabId)
  else await pinCurrentWebTab()
  await chrome.tabs.create({ url: chrome.runtime.getURL('workspace.html') })
}

/** Non-gesture path — may fail if not called from a click handler. Prefer `openSidePanelWithGesture`. */
export async function openSidePanel(): Promise<void> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id) return
  openSidePanelWithGesture(tab.id, tab.windowId)
}

export async function openOptionsPage(section?: string): Promise<void> {
  if (section) {
    await chrome.storage.local.set({ [STORAGE.openSection]: section })
  }
  const optionsUrl = chrome.runtime.getURL('options.html')
  const hashUrl = section ? `${optionsUrl}#${section}` : optionsUrl
  const existing = await chrome.tabs.query({ url: `${optionsUrl}*` })
  if (existing.length > 0 && existing[0]?.id) {
    await chrome.tabs.update(existing[0].id, { url: hashUrl, active: true })
    if (existing[0].windowId != null) {
      await chrome.windows.update(existing[0].windowId, { focused: true })
    }
    return
  }
  await chrome.runtime.openOptionsPage()
  if (section) {
    const opened = await chrome.tabs.query({ url: `${optionsUrl}*`, active: true })
    const tab = opened[0]
    if (tab?.id) await chrome.tabs.update(tab.id, { url: hashUrl })
  }
}

/** Reliable from extension popup — always opens a new options tab. */
export function openOptionsPageFromPopup(section?: string): void {
  if (section) {
    void chrome.storage.local.set({ [STORAGE.openSection]: section })
  }
  const url = chrome.runtime.getURL(section ? `options.html#${section}` : 'options.html')
  chrome.tabs.create({ url })
}

export async function openToolkitPage(): Promise<void> {
  await pinCurrentWebTab()
  await openOptionsPage('toolkit')
}

export async function openToolkitPageWithRunResult(result: unknown): Promise<void> {
  await pinCurrentWebTab()
  await chrome.storage.local.set({ [STORAGE.openToolkitRunResult]: result })
  await openOptionsPage('toolkit')
}

export async function openJsonFormatPage(): Promise<void> {
  await pinCurrentWebTab()
  await chrome.storage.local.set({ [STORAGE.openJsonDrawer]: true })
  await openOptionsPage('toolkit')
}
