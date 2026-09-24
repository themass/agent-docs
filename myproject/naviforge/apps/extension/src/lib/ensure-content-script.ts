function isRestrictedUrl(url: string | undefined): boolean {
  if (!url) return true
  return (
    url.startsWith('chrome://') ||
    url.startsWith('chrome-extension://') ||
    url.startsWith('devtools://') ||
    url.startsWith('edge://') ||
    url.startsWith('about:')
  )
}

async function pingContent(tabId: number): Promise<boolean> {
  try {
    const res = await chrome.tabs.sendMessage(tabId, {
      type: 'PAGE_CONTROL',
      action: 'ping',
    })
    return !!(res as { ok?: boolean } | undefined)?.ok
  } catch {
    return false
  }
}

/** Inject content script if missing (common after extension reload without page refresh). */
export async function ensureContentScript(
  tabId: number
): Promise<{ ok: true } | { ok: false; error: string }> {
  if (await pingContent(tabId)) return { ok: true }

  const tab = await chrome.tabs.get(tabId)
  if (isRestrictedUrl(tab.url)) {
    return {
      ok: false,
      error: `无法注入此页面（${tab.url ?? 'unknown'}）。请打开普通 http(s) 页面（如 http://localhost:4177）后重试。`,
    }
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content-scripts/content.js'],
    })
  } catch (e) {
    return {
      ok: false,
      error: `注入 content script 失败: ${(e as Error).message}。请刷新页面后再试。`,
    }
  }

  await new Promise((r) => setTimeout(r, 50))
  if (await pingContent(tabId)) return { ok: true }
  return {
    ok: false,
    error:
      'Could not establish connection. Receiving end does not exist. 请刷新当前标签页后再点 Run（扩展更新后旧页没有 content script）。',
  }
}

export function isToolkitRestrictedUrl(url: string | undefined): boolean {
  return isRestrictedUrl(url)
}
