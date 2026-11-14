const ORIGINS = ['http://*/*', 'https://*/*'] as const

const RESTRICTED_PREFIXES = ['chrome://', 'chrome-extension://', 'devtools://', 'edge://', 'about:']

export function originPatternForUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return null
    return `${parsed.origin}/*`
  } catch {
    return null
  }
}

export function isHttpPageUrl(url: string | undefined): boolean {
  if (!url) return false
  if (RESTRICTED_PREFIXES.some((prefix) => url.startsWith(prefix))) return false
  return url.startsWith('http://') || url.startsWith('https://')
}

export async function hasBroadHostAccess(): Promise<boolean> {
  try {
    return await chrome.permissions.contains({ origins: [...ORIGINS] })
  } catch {
    return false
  }
}

export async function hasHostAccessForUrl(url: string | undefined): Promise<boolean> {
  if (!url) return false
  if (await hasBroadHostAccess()) return true
  const pattern = originPatternForUrl(url)
  if (!pattern) return false
  try {
    return await chrome.permissions.contains({ origins: [pattern] })
  } catch {
    return false
  }
}

/** Request http(s) access before Agent touches arbitrary sites. */
export async function requestBroadHostAccess(): Promise<boolean> {
  try {
    return await chrome.permissions.request({ origins: [...ORIGINS] })
  } catch {
    return false
  }
}

export async function requestHostAccessForUrl(url: string | undefined): Promise<boolean> {
  if (!url) return false
  if (await hasHostAccessForUrl(url)) return true
  const pattern = originPatternForUrl(url)
  if (!pattern) return false
  try {
    return await chrome.permissions.request({ origins: [pattern] })
  } catch {
    return false
  }
}

export function hostAccessPageUrl(): string {
  return chrome.runtime.getURL('host-access.html')
}

export async function openHostAccessPage(): Promise<void> {
  await chrome.tabs.create({ url: hostAccessPageUrl(), active: true })
}

/** Check only — does not call permissions.request (no user gesture in SW after messaging). */
export async function checkHostAccessForTab(
  tabId: number
): Promise<{ ok: true } | { ok: false; error: string }> {
  let tab: chrome.tabs.Tab
  try {
    tab = await chrome.tabs.get(tabId)
  } catch {
    return { ok: false, error: '标签页已关闭，请重新打开网页后再试。' }
  }
  const url = tab.url
  if (!isHttpPageUrl(url)) {
    return { ok: false, error: '浏览器内部页无法使用网页工具，请切换到普通 https 页面。' }
  }
  if (await hasHostAccessForUrl(url)) return { ok: true }
  return {
    ok: false,
    error:
      '尚未允许 NaviForge 访问网站。将打开授权页，请点击「允许访问所有网站」（一次即可覆盖全部 http/https 页面）。',
  }
}

/**
 * Call only from a user-gesture context (commands, contextMenus, extension page click).
 * chrome.permissions.request fails silently if invoked after content-script messaging.
 */
export async function promptBroadHostAccessIfNeeded(): Promise<boolean> {
  if (await hasBroadHostAccess()) return true
  return requestBroadHostAccess()
}
