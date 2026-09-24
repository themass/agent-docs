export async function sendPageControl<T>(
  tabId: number,
  action: string,
  payload?: Record<string, unknown>
): Promise<T> {
  const message = { type: 'PAGE_CONTROL', action, payload, targetTabId: tabId }
  try {
    return (await chrome.tabs.sendMessage(tabId, message)) as T
  } catch {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content-scripts/content.js'],
    })
    return (await chrome.tabs.sendMessage(tabId, message)) as T
  }
}
