import { ensureContentScript, isToolkitRestrictedUrl } from './ensure-content-script.js'

/** Open the searchable toolkit overlay on a web tab (not via runtime.sendMessage to self). */
export async function showToolkitPaletteOnTab(
  tabId: number
): Promise<{ ok: boolean; error?: string }> {
  const tab = await chrome.tabs.get(tabId)
  if (isToolkitRestrictedUrl(tab.url)) {
    return { ok: false, error: '请先打开普通网页' }
  }
  const ensured = await ensureContentScript(tabId)
  if (!ensured.ok) return { ok: false, error: ensured.error }

  try {
    await chrome.tabs.sendMessage(tabId, {
      type: 'PAGE_CONTROL',
      action: 'show_toolkit_palette',
      targetTabId: tabId,
      payload: {},
    })
    return { ok: true }
  } catch (error) {
    return { ok: false, error: (error as Error).message }
  }
}
