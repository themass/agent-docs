import type { DomMarkTopnResult } from '@naviforge/dom-plane'
import type { ToolResult } from '@naviforge/shared'

import { createChromeDomPlane } from './chrome-dom-plane'
import { STORAGE } from './settings'

const RESTRICTED_PREFIXES = ['chrome://', 'chrome-extension://', 'devtools://', 'edge://', 'about:']

export type ToolkitTabRef = {
  id: number
  title?: string
  url?: string
  windowId?: number
  active?: boolean
}

export function isToolkitPageUrl(url: string | undefined): boolean {
  if (!url) return false
  return !RESTRICTED_PREFIXES.some((prefix) => url.startsWith(prefix))
}

function isNaviForgeSurface(url: string | undefined): boolean {
  if (!url) return false
  return url.startsWith(chrome.runtime.getURL(''))
}

function webTabs(tabs: chrome.tabs.Tab[]): chrome.tabs.Tab[] {
  return tabs.filter((tab) => tab.id != null && isToolkitPageUrl(tab.url) && !isNaviForgeSurface(tab.url))
}

function byRecentAccess(a: chrome.tabs.Tab, b: chrome.tabs.Tab): number {
  return (b.lastAccessed ?? 0) - (a.lastAccessed ?? 0)
}

async function readPinnedTabId(): Promise<number | undefined> {
  const saved = await chrome.storage.local.get(STORAGE.toolkitTabId)
  const id = saved[STORAGE.toolkitTabId]
  return typeof id === 'number' ? id : undefined
}

export async function setPinnedToolkitTabId(tabId: number): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.toolkitTabId]: tabId })
}

export async function listToolkitTabs(): Promise<ToolkitTabRef[]> {
  const tabs = webTabs(await chrome.tabs.query({}))
  return tabs
    .sort(byRecentAccess)
    .map((tab) => ({
      id: tab.id!,
      title: tab.title,
      url: tab.url,
      windowId: tab.windowId,
      active: tab.active,
    }))
}

function isWebTarget(tab: { id?: number; url?: string } | null | undefined): boolean {
  return Boolean(tab?.id && isToolkitPageUrl(tab.url))
}

/** Focused http(s) page wins; pin is only for when Control Center / popup isn't a web tab. */
export function preferLiveWebTab<T extends { id?: number; url?: string }>(
  focused: T | undefined,
  pinned: T | undefined,
  recent: T[]
): T | undefined {
  if (focused && isWebTarget(focused)) return focused
  if (pinned && isWebTarget(pinned)) return pinned
  return recent.find((tab) => isWebTarget(tab))
}

function isLiveWebTab(tab: chrome.tabs.Tab | undefined): tab is chrome.tabs.Tab {
  return Boolean(tab?.id && isWebTarget(tab) && !isNaviForgeSurface(tab.url))
}

/** The page under the extension menu (popup) or the last focused normal page. */
export async function snapshotCurrentWebTab(): Promise<chrome.tabs.Tab | null> {
  const [current] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (isLiveWebTab(current)) return current
  const [last] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  if (isLiveWebTab(last)) return last
  const recent = webTabs(await chrome.tabs.query({})).sort(byRecentAccess)
  return recent[0] ?? null
}

export async function pinCurrentWebTab(): Promise<chrome.tabs.Tab | null> {
  const tab = await snapshotCurrentWebTab()
  if (tab?.id) await setPinnedToolkitTabId(tab.id)
  return tab
}

/** Explicit tab from the popup wins; otherwise the live page, then pin. */
export async function resolveToolkitTab(explicitTabId?: number): Promise<chrome.tabs.Tab | null> {
  if (explicitTabId != null) {
    try {
      const tab = await chrome.tabs.get(explicitTabId)
      if (isLiveWebTab(tab) && tab.id != null) {
        await setPinnedToolkitTabId(tab.id)
        return tab
      }
    } catch {
      // tab closed — fall through
    }
  }
  const [focusedActive] = await chrome.tabs.query({ active: true, lastFocusedWindow: true })
  let pinned: chrome.tabs.Tab | undefined
  const pinnedId = await readPinnedTabId()
  if (pinnedId != null) {
    try {
      pinned = await chrome.tabs.get(pinnedId)
    } catch {
      // tab closed
    }
  }
  const recent = webTabs(await chrome.tabs.query({})).sort(byRecentAccess)
  const picked = preferLiveWebTab(focusedActive, pinned, recent) ?? null
  if (picked?.id) await setPinnedToolkitTabId(picked.id)
  return picked
}

/** Pin to the tab you were just viewing (works while toolkit options tab is focused). */
export async function bindToolkitToRecentWebTab(): Promise<chrome.tabs.Tab | null> {
  const tabs = webTabs(await chrome.tabs.query({ lastFocusedWindow: true })).sort(byRecentAccess)
  const tab = tabs[0] ?? null
  if (tab?.id) await setPinnedToolkitTabId(tab.id)
  return tab
}

export async function switchToolkitTab(tabId: number, windowId?: number): Promise<chrome.tabs.Tab | null> {
  await chrome.tabs.update(tabId, { active: true })
  if (windowId != null) await chrome.windows.update(windowId, { focused: true })
  await setPinnedToolkitTabId(tabId)
  try {
    return await chrome.tabs.get(tabId)
  } catch {
    return null
  }
}

/** @deprecated use resolveToolkitTab */
export async function getToolkitTargetTab(): Promise<chrome.tabs.Tab | null> {
  return resolveToolkitTab()
}

export function googleTranslateUrl(pageUrl: string, targetLang = 'zh-CN'): string {
  const params = new URLSearchParams({ sl: 'auto', tl: targetLang, u: pageUrl })
  return `https://translate.google.com/translate?${params}`
}

export async function downloadDataUrl(dataUrl: string, filename: string): Promise<void> {
  await chrome.downloads.download({ url: dataUrl, filename, saveAs: true })
}

export function buildExtractJsonl(
  items: Array<{ title: string; url?: string; fields?: Record<string, string> }>
): string {
  return items
    .map((item) =>
      JSON.stringify({
        title: item.title,
        url: item.url,
        ...item.fields,
      })
    )
    .join('\n')
}

export function downloadTextFile(text: string, filename: string): void {
  const type = filename.endsWith('.txt') ? 'text/plain;charset=utf-8' : 'application/jsonl'
  const blob = new Blob([text], { type })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

/** Service-worker safe download (no DOM). */
export async function downloadTextViaDownloads(text: string, filename: string): Promise<void> {
  const url = `data:application/x-ndjson;charset=utf-8,${encodeURIComponent(text)}`
  await chrome.downloads.download({ url, filename, saveAs: true })
}

export async function toolkitExtractAndDownload(
  tabId: number,
  n = 10
): Promise<{ ok: boolean; count?: number; error?: string }> {
  const extracted = await toolkitExtract(tabId, n)
  if (!extracted.ok) return { ok: false, error: extracted.error.message }
  await downloadTextViaDownloads(
    buildExtractJsonl(extracted.data.items),
    `naviforge-extract-${Date.now()}.jsonl`
  )
  return { ok: true, count: extracted.data.items.length }
}

function domForTab(tabId: number) {
  return createChromeDomPlane(() => tabId)
}

export async function toolkitScreenshot(tabId: number): Promise<ToolResult<{ dataUrl: string }>> {
  return domForTab(tabId).screenshot?.() ?? { ok: false, error: { code: 'unsupported', message: 'screenshot unavailable', recoverable: false } }
}

export async function toolkitFullPageScreenshot(
  tabId: number
): Promise<ToolResult<{ dataUrl: string; width: number; height: number; slices: number }>> {
  return (
    domForTab(tabId).screenshotFullPage?.() ?? {
      ok: false,
      error: { code: 'unsupported', message: 'full-page screenshot unavailable', recoverable: false },
    }
  )
}

export async function toolkitExtract(
  tabId: number,
  n: number
): Promise<ToolResult<DomMarkTopnResult>> {
  return (
    domForTab(tabId).extractContent?.(n) ?? {
      ok: false,
      error: { code: 'unsupported', message: 'extract unavailable', recoverable: false },
    }
  )
}

export async function toolkitMarkTopn(
  tabId: number,
  n: number
): Promise<ToolResult<DomMarkTopnResult>> {
  return (
    domForTab(tabId).markTopn?.(n, { showHints: true }) ?? {
      ok: false,
      error: { code: 'unsupported', message: 'mark unavailable', recoverable: false },
    }
  )
}

export async function toolkitOpenTranslate(
  tab: chrome.tabs.Tab,
  targetLang?: string
): Promise<{
  ok: boolean
  error?: string
  mode?: 'restore' | 'gtx'
  translated?: number
  limited?: boolean
  lang?: string
}> {
  if (!tab.id || !tab.url || !isToolkitPageUrl(tab.url)) {
    return { ok: false, error: '当前标签无法翻译（仅支持 http/https 页面）' }
  }
  const { isTranslateLangId, translateTabInPlace } = await import('./page-translate')
  const saved = await chrome.storage.local.get(STORAGE.translateTargetLang)
  const stored = saved[STORAGE.translateTargetLang]
  const lang =
    targetLang && isTranslateLangId(targetLang)
      ? targetLang
      : typeof stored === 'string' && isTranslateLangId(stored)
        ? stored
        : 'zh-CN'
  await chrome.tabs.update(tab.id, { active: true })
  if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })
  const result = await translateTabInPlace(tab.id, lang)
  if (!result.ok) return { ok: false, error: result.error ?? '翻译失败', lang }
  return {
    ok: true,
    mode: result.mode,
    translated: result.translated,
    limited: result.limited,
    lang,
  }
}

export function describeSavedShot(
  path: string,
  workspaceRoot?: string
): { title: string; location: string; hint: string; inDownloads: boolean } {
  const inDownloads = path.startsWith('Downloads/')
  const location =
    !inDownloads && workspaceRoot ? `${workspaceRoot.replace(/\/$/, '')}/${path}` : path
  return {
    title: '截图已保存',
    location,
    hint: inDownloads
      ? '本机助手未连接，文件在浏览器下载目录的 NaviForge 文件夹'
      : '也可在插件菜单点「打开工作台」查看',
    inDownloads,
  }
}

/** Rich toast with path link + open file / folder buttons (palette · shortcuts). */
export async function flashSavedShotFeedback(
  tabId: number,
  result: { path?: string; downloadId?: number },
  title: string
): Promise<void> {
  const path = result.path ?? title
  const { ensureLocalHelper } = await import('./local-workspace')
  const helper = await ensureLocalHelper()
  const described = describeSavedShot(path, helper.ok ? helper.workspaceRoot : undefined)
  const inDownloads = Boolean(result.downloadId) || described.inDownloads
  await flashCommandFeedback(
    {
      title,
      location: described.location,
      hint: described.hint,
      revealPath: inDownloads ? undefined : result.path,
      downloadId: result.downloadId,
    },
    tabId
  )
}

export type CommandToast = {
  title: string
  location?: string
  hint?: string
  revealPath?: string
  downloadId?: number
  ttlMs?: number
}

function paintCommandToast(payload: string | CommandToast): void {
  const id = 'naviforge-toolkit-toast'
  document.getElementById(id)?.remove()
  const el = document.createElement('div')
  el.id = id
  el.setAttribute('role', 'status')
  Object.assign(el.style, {
    position: 'fixed',
    top: '16px',
    right: '16px',
    zIndex: '2147483647',
    maxWidth: '380px',
    padding: '12px 14px',
    background: '#111',
    color: '#fff',
    font: '13px/1.4 system-ui,sans-serif',
    borderRadius: '8px',
    boxShadow: '0 8px 24px rgba(0,0,0,.25)',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  })
  const addBtn = (label: string, onClick: () => void): HTMLButtonElement => {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.textContent = label
    Object.assign(btn.style, {
      border: '0',
      borderRadius: '6px',
      padding: '6px 10px',
      background: '#70a91d',
      color: '#111',
      font: '650 12px system-ui,sans-serif',
      cursor: 'pointer',
    })
    btn.addEventListener('click', (event) => {
      event.preventDefault()
      event.stopPropagation()
      onClick()
    })
    return btn
  }
  if (typeof payload === 'string') {
    el.textContent = payload
  } else {
    const title = document.createElement('div')
    title.style.fontWeight = '650'
    title.textContent = payload.title
    el.append(title)
    if (payload.location) {
      const loc = document.createElement('div')
      Object.assign(loc.style, {
        font: '11px/1.4 ui-monospace,monospace',
        wordBreak: 'break-all',
      })
      if (payload.revealPath) {
        const link = document.createElement('button')
        link.type = 'button'
        link.textContent = payload.location
        Object.assign(link.style, {
          border: '0',
          background: 'transparent',
          padding: '0',
          color: '#b7e08b',
          textDecoration: 'underline',
          cursor: 'pointer',
          font: 'inherit',
          textAlign: 'left',
        })
        link.addEventListener('click', (event) => {
          event.preventDefault()
          event.stopPropagation()
          void chrome.runtime.sendMessage({
            type: 'WORKSPACE_REVEAL',
            path: payload.revealPath!,
          })
        })
        loc.append(link)
      } else {
        loc.textContent = payload.location
        loc.style.color = '#ddd'
      }
      el.append(loc)
    }
    if (payload.hint) {
      const hint = document.createElement('div')
      hint.textContent = payload.hint
      Object.assign(hint.style, { fontSize: '11px', color: '#aaa' })
      el.append(hint)
    }
    const row = document.createElement('div')
    Object.assign(row.style, { display: 'flex', gap: '8px', flexWrap: 'wrap' })
    if (payload.revealPath) {
      const file = payload.revealPath
      const slash = file.lastIndexOf('/')
      const dir = slash > 0 ? file.slice(0, slash) : file
      row.append(
        addBtn('打开文件', () => {
          void chrome.runtime.sendMessage({ type: 'WORKSPACE_REVEAL', path: file })
        }),
        addBtn('打开文件夹', () => {
          void chrome.runtime.sendMessage({ type: 'WORKSPACE_REVEAL', path: dir })
        })
      )
      row.lastChild && Object.assign((row.lastChild as HTMLElement).style, { background: '#333', color: '#fff' })
    } else if (payload.downloadId != null) {
      const downloadId = payload.downloadId
      row.append(
        addBtn('在下载中显示', () => {
          void chrome.runtime.sendMessage({ type: 'DOWNLOADS_SHOW', downloadId })
        })
      )
    }
    if (row.childNodes.length) el.append(row)
  }
  document.documentElement.appendChild(el)
  const ttl = typeof payload === 'string' ? 4000 : (payload.ttlMs ?? 12000)
  setTimeout(() => el.remove(), ttl)
}

/** Toast on page when possible; otherwise badge on the extension icon. */
export async function flashCommandFeedback(
  message: string | CommandToast,
  tabId?: number
): Promise<void> {
  if (tabId != null) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        func: paintCommandToast,
        args: [message],
      })
      return
    } catch {
      // restricted page — fall through to badge
    }
  }
  const title = typeof message === 'string' ? message : `${message.title} ${message.location ?? ''}`.trim()
  try {
    await chrome.action.setBadgeText({ text: '!' })
    await chrome.action.setBadgeBackgroundColor({ color: '#b45309' })
    await chrome.action.setTitle({ title: `NaviForge：${title}` })
    setTimeout(() => {
      void chrome.action.setBadgeText({ text: '' })
      void chrome.action.setTitle({ title: 'NaviForge' })
    }, 5000)
  } catch {
    // ignore
  }
}

export async function toolkitCaptureVisible(
  tabId?: number
): Promise<{ ok: boolean; error?: string; path?: string; downloadId?: number }> {
  const tab = await resolveToolkitTab(tabId)
  if (!tab?.id) return { ok: false, error: '没有可截图的网页标签，请先打开目标页面' }
  const shot = await toolkitScreenshot(tab.id)
  if (!shot.ok || !shot.data?.dataUrl) {
    return { ok: false, error: !shot.ok ? shot.error.message : '截图失败' }
  }
  const { downloadFallback, saveWorkspaceShot } = await import('./local-workspace')
  const saved = await saveWorkspaceShot({ kind: 'visible', dataUrl: shot.data.dataUrl, tool: 'toolkit.visible' })
  if (saved?.relativePath) return { ok: true, path: saved.relativePath }
  try {
    const filename = `shots/naviforge-visible-${Date.now()}.png`
    const downloadId = await downloadFallback(shot.data.dataUrl, filename)
    return { ok: true, path: `Downloads/NaviForge/${filename}`, downloadId }
  } catch (error) {
    return { ok: false, error: `无法保存截图：${(error as Error).message}。请先连接本机助手。` }
  }
}

export async function toolkitCaptureFullPage(
  tabId?: number
): Promise<{ ok: boolean; error?: string; path?: string; downloadId?: number }> {
  const tab = await resolveToolkitTab(tabId)
  if (!tab?.id) return { ok: false, error: '没有可截图的网页标签，请先打开目标页面' }
  const shot = await toolkitFullPageScreenshot(tab.id)
  if (!shot.ok || !shot.data?.dataUrl) {
    return { ok: false, error: !shot.ok ? shot.error.message : '全页截图失败' }
  }
  const { downloadFallback, saveWorkspaceShot } = await import('./local-workspace')
  const saved = await saveWorkspaceShot({ kind: 'fullpage', dataUrl: shot.data.dataUrl, tool: 'toolkit.fullpage' })
  if (saved?.relativePath) return { ok: true, path: saved.relativePath }
  try {
    const filename = `shots/naviforge-fullpage-${Date.now()}.png`
    const downloadId = await downloadFallback(shot.data.dataUrl, filename)
    return { ok: true, path: `Downloads/NaviForge/${filename}`, downloadId }
  } catch (error) {
    return { ok: false, error: `无法保存截图：${(error as Error).message}。请先连接本机助手。` }
  }
}
