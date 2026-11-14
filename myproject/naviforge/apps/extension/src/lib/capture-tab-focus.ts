/** Bring the target tab's window to the OS foreground before captureVisibleTab. */
export async function focusTabForCapture(tabId: number): Promise<chrome.tabs.Tab> {
  let tab = await chrome.tabs.get(tabId)
  if (tab.windowId != null) {
    await chrome.windows.update(tab.windowId, { focused: true }).catch(() => undefined)
  }
  tab = (await chrome.tabs.update(tabId, { active: true })) ?? tab
  // macOS + side panel: compositor needs a beat before Chrome grants capture.
  await new Promise((resolve) => setTimeout(resolve, 180))
  if (tab.windowId == null) throw new Error('截图目标标签没有窗口')
  return tab
}
