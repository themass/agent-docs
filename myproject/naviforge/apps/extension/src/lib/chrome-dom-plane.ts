import type {
  DomContentItem,
  DomMarkTopnResult,
  DomPlane,
  DomSnapshot,
  DomExtractResult,
  PageSignalCollectPayload,
  SnapshotMode,
} from '@naviforge/dom-plane'
import type { ToolResult } from '@naviforge/shared'

import {
  captureFullPageTab,
  type FullPageCaptureResult,
} from './capture-full-page-runner'
import { friendlyCaptureError } from './capture-full-page'
import { isPageCspEvalError } from './isolated-script'
import { printTabToPdf } from './print-tab-pdf'

type StatePayload = DomSnapshot

// ponytail: Chrome allows ~2 captureVisibleTab/sec. Serialize and gap; retry once on quota.
const MIN_CAPTURE_GAP_MS = 550
let captureLock: Promise<void> = Promise.resolve()
let lastCaptureAt = 0

async function captureVisibleTabPng(windowId: number): Promise<string> {
  let release: () => void = () => {}
  const previous = captureLock
  captureLock = new Promise<void>((resolve) => {
    release = resolve
  })
  await previous
  try {
    const wait = MIN_CAPTURE_GAP_MS - (Date.now() - lastCaptureAt)
    if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait))
    lastCaptureAt = Date.now()
    try {
      return await chrome.tabs.captureVisibleTab(windowId, { format: 'png' })
    } catch (error) {
      if (!/MAX_CAPTURE_VISIBLE_TAB|quota/i.test((error as Error).message)) throw error
      await new Promise((resolve) => setTimeout(resolve, MIN_CAPTURE_GAP_MS))
      lastCaptureAt = Date.now()
      return await chrome.tabs.captureVisibleTab(windowId, { format: 'png' })
    }
  } finally {
    release()
  }
}

async function send<T>(
  targetTabId: number,
  action: string,
  payload?: Record<string, unknown>,
  timeoutMs = 15_000
): Promise<T> {
  const message = {
    type: 'PAGE_CONTROL',
    action,
    targetTabId,
    payload,
  }

  const withTimeout = async (deliver: () => Promise<T>): Promise<T> => {
    if (timeoutMs <= 0) return deliver()
    return Promise.race([
      deliver(),
      new Promise<T>((_, reject) => {
        setTimeout(() => reject(new Error(`timeout after ${timeoutMs}ms`)), timeoutMs)
      }),
    ])
  }

  // A service worker cannot route chrome.runtime.sendMessage back into its own
  // onMessage listener. Background-hosted runs must send directly to the tab.
  if (typeof document === 'undefined') {
    return withTimeout(async () => {
      try {
        return (await chrome.tabs.sendMessage(targetTabId, message)) as T
      } catch {
        await chrome.scripting.executeScript({
          target: { tabId: targetTabId },
          files: ['content-scripts/content.js'],
        })
        return (await chrome.tabs.sendMessage(targetTabId, message)) as T
      }
    })
  }

  return withTimeout(() => chrome.runtime.sendMessage(message) as Promise<T>)
}

/** `extract_content` and `mark_topn` return the same record report. */
async function recordReport(
  tabId: number,
  action: 'mark_topn' | 'extract_content',
  payload: Record<string, unknown>
): Promise<ToolResult<DomMarkTopnResult>> {
  const res = await send<{
    success: boolean
    marked?: number
    candidates?: number
    items?: DomContentItem[]
    strategy?: string
    profileId?: string
    shortfall?: string
    error?: string
  }>(tabId, action, payload)
  if (!res?.success) {
    return {
      ok: false,
      error: {
        code: `${action}_failed`,
        message: res?.error ?? `${action} failed — scroll the list into view and retry`,
        recoverable: true,
      },
    }
  }
  return {
    ok: true,
    data: {
      marked: res.marked ?? 0,
      candidates: res.candidates ?? 0,
      items: res.items ?? [],
      strategy: res.strategy,
      profileId: res.profileId,
      shortfall: res.shortfall,
    },
  }
}

/** DomPlane over chrome.runtime → content script PageController (isolated world). */
export function createChromeDomPlane(getTabId: () => number): DomPlane {
  let lastRevision = 0
  const tab = () => getTabId()

  function stale(revision: number): ToolResult<{ message: string }> | null {
    if (revision !== lastRevision) {
      return {
        ok: false,
        error: {
          code: 'stale_revision',
          message: `revision ${revision} != ${lastRevision}`,
          recoverable: true,
        },
      }
    }
    return null
  }

  return {
    async snapshot(opts?: { mode?: SnapshotMode }): Promise<ToolResult<DomSnapshot>> {
      const res = await send<{ success: boolean; data?: StatePayload; error?: string }>(
        getTabId(),
        'get_browser_state',
        { showHints: false, mode: opts?.mode }
      )
      if (!res?.success || !res.data) {
        return {
          ok: false,
          error: {
            code: 'snapshot_failed',
            message: res?.error ?? 'snapshot failed',
            recoverable: true,
          },
        }
      }
      lastRevision = res.data.revision
      return { ok: true, data: res.data }
    },

    async readPage(opts?: { timeoutMs?: number }) {
      const timeoutMs = Math.min(30_000, Math.max(1_000, opts?.timeoutMs ?? 15_000))
      try {
        const res = await send<{
          success: boolean
          data?: {
            text: string
            source: string
            truncated: boolean
            title: string
            url: string
          }
          error?: string
        }>(getTabId(), 'read_page', {}, timeoutMs)
        if (!res?.success || !res.data) {
          return {
            ok: false,
            error: {
              code: 'read_page_failed',
              message: res?.error ?? 'read_page failed',
              recoverable: true,
            },
          }
        }
        return { ok: true, data: res.data }
      } catch (error) {
        const message = (error as Error).message
        if (/timeout/i.test(message)) {
          return {
            ok: false,
            error: {
              code: 'timeout',
              message: `read_page timed out after ${timeoutMs}ms`,
              recoverable: true,
            },
          }
        }
        throw error
      }
    },

    async toMarkdown() {
      const res = await send<{
        success: boolean
        data?: { markdown: string; title: string; url: string; source: string }
        error?: string
      }>(getTabId(), 'to_markdown', {})
      if (!res?.success || !res.data) {
        return {
          ok: false,
          error: {
            code: 'to_markdown_failed',
            message: res?.error ?? 'to_markdown failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: res.data }
    },

    async click(index, revision, framePath?): Promise<ToolResult<{ message: string }>> {
      if (revision !== lastRevision) {
        return {
          ok: false,
          error: {
            code: 'stale_revision',
            message: `revision ${revision} != ${lastRevision}`,
            recoverable: true,
          },
        }
      }
      const res = await send<{ success: boolean; message?: string; error?: string }>(
        getTabId(),
        'click_element',
        { index, framePath }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'click_failed',
            message: res?.message ?? res?.error ?? 'click failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async type(index, text, revision): Promise<ToolResult<{ message: string }>> {
      if (revision !== lastRevision) {
        return {
          ok: false,
          error: {
            code: 'stale_revision',
            message: `revision ${revision} != ${lastRevision}`,
            recoverable: true,
          },
        }
      }
      const res = await send<{ success: boolean; message?: string; error?: string }>(
        getTabId(),
        'input_text',
        { index, text }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'type_failed',
            message: res?.message ?? res?.error ?? 'type failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async selector(index, revision): Promise<ToolResult<{ selector?: string }>> {
      if (revision !== lastRevision) {
        return {
          ok: false,
          error: {
            code: 'stale_revision',
            message: `revision ${revision} != ${lastRevision}`,
            recoverable: true,
          },
        }
      }
      const res = await send<{ success: boolean; selector?: string; error?: string }>(
        getTabId(),
        'get_selector',
        { index }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'selector_failed',
            message: res?.error ?? 'selector lookup failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { selector: res.selector } }
    },

    async clickSelector(selector): Promise<ToolResult<{ message: string }>> {
      const res = await send<{ success: boolean; message?: string; error?: string }>(
        getTabId(),
        'click_selector',
        { selector }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'selector_click_failed',
            message: res?.error ?? 'selector click failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async typeSelector(selector, text): Promise<ToolResult<{ message: string }>> {
      const res = await send<{ success: boolean; message?: string; error?: string }>(
        getTabId(),
        'input_selector',
        { selector, text }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'selector_type_failed',
            message: res?.error ?? 'selector input failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async highlight(targets, revision) {
      if (revision != null && revision !== lastRevision) {
        return {
          ok: false,
          error: {
            code: 'stale_revision',
            message: `revision ${revision} != ${lastRevision}`,
            recoverable: true,
          },
        }
      }
      const res = await send<{ success: boolean; marked?: number; missed?: string[]; error?: string }>(
        getTabId(),
        'highlight',
        { targets }
      )
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'highlight_failed',
            message:
              res?.error ??
              (res?.missed?.length
                ? `highlight missed: ${res.missed.join(', ')}`
                : 'highlight failed — indexes may be stale, snapshot again'),
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { marked: res.marked ?? 0 } }
    },

    async markTopn(n, opts) {
      return recordReport(getTabId(), 'mark_topn', { n, showHints: opts?.showHints })
    },

    async extractContent(n) {
      return recordReport(getTabId(), 'extract_content', { n })
    },

    async markItems(items) {
      const res = await send<{
        success: boolean
        marked?: number
        missed?: number[]
        error?: string
      }>(getTabId(), 'mark_items', { items })
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'mark_items_failed',
            message: res?.error ?? 'mark_items failed — re-run extract_content first',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { marked: res.marked ?? 0, missed: res.missed } }
    },

    async clearHighlights() {
      const res = await send<{ success: boolean; error?: string }>(getTabId(), 'clear_highlights')
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'clear_highlights_failed',
            message: res?.error ?? 'clear failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { cleared: true } }
    },

    async inject(opts) {
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'inject', {
        injectKind: opts.kind,
        code: opts.code,
        allowScript: opts.allowScript === true,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'inject_failed',
            message: res?.error ?? 'inject failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async executeJs(opts) {
      const res = await send<{ success: boolean; result?: unknown; error?: string }>(
        getTabId(),
        'execute_js',
        {
          code: opts.code,
          timeout_ms: opts.timeoutMs,
          allowScript: true,
        }
      )
      if (!res?.success) {
        const message = res?.error ?? 'execute_js failed'
        return {
          ok: false,
          error: {
            code: isPageCspEvalError(message) ? 'csp_eval_blocked' : 'execute_js_failed',
            message,
            recoverable: !isPageCspEvalError(message),
          },
        }
      }
      return { ok: true, data: { result: res.result ?? null } }
    },

    async extractDom(opts) {
      const res = await send<{ success: boolean; data?: DomExtractResult; error?: string }>(
        getTabId(),
        'extract_dom',
        { kind: opts?.kind, limit: opts?.limit }
      )
      if (!res?.success || !res.data) {
        return {
          ok: false,
          error: {
            code: 'extract_dom_failed',
            message: res?.error ?? 'extract_dom failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: res.data }
    },

    async navigate(action, url) {
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'navigate', {
        action,
        url,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'navigate_failed',
            message: res?.error ?? 'navigate failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async scroll(opts) {
      const res = await send<{
        success: boolean
        message?: string
        error?: string
        scrollY?: number
        atBottom?: boolean
        target?: string
        delta?: number
      }>(getTabId(), 'scroll', opts)
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'scroll_failed',
            message: res?.error ?? 'scroll failed',
            recoverable: true,
          },
        }
      }
      return {
        ok: true,
        data: {
          message: res.message ?? 'ok',
          scrollY: res.scrollY,
          atBottom: res.atBottom,
          target: res.target,
          delta: res.delta,
        },
      }
    },

    async wait(opts) {
      if (opts.kind === 'download') {
        const { waitForTabDownload } = await import('./download-monitor.js')
        const timeoutMs = Math.min(120_000, Math.max(5_000, opts.timeoutMs ?? 60_000))
        const sinceMs = Date.now() - 2_000
        const result = await waitForTabDownload(tab(), { sinceMs, timeoutMs })
        if (!result.ok) {
          return {
            ok: false,
            error: {
              code: result.error.includes('within') ? 'timeout' : 'download_failed',
              message: result.error,
              recoverable: true,
            },
          }
        }
        return {
          ok: true,
          data: { message: `download complete: ${result.filename} (id=${result.downloadId})` },
        }
      }
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'wait', {
        waitKind: opts.kind,
        text: opts.text,
        timeout_ms: opts.timeoutMs,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'wait_failed',
            message: res?.error ?? 'wait failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async press(key, modifiers) {
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'press', {
        key,
        modifiers,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: {
            code: 'press_failed',
            message: res?.error ?? 'press failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async select(index, value, revision) {
      const staleResult = stale(revision)
      if (staleResult) return staleResult
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'select_option', {
        index,
        value,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: { code: 'select_failed', message: res?.error ?? 'select failed', recoverable: true },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async check(index, checked, revision) {
      const staleResult = stale(revision)
      if (staleResult) return staleResult
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'set_checked', {
        index,
        checked,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: { code: 'check_failed', message: res?.error ?? 'check failed', recoverable: true },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async upload(index, filename, contentBase64, revision) {
      const staleResult = stale(revision)
      if (staleResult) return staleResult
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'upload_file', {
        index,
        filename,
        contentBase64,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: { code: 'upload_failed', message: res?.error ?? 'upload failed', recoverable: true },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async hover(index, revision) {
      const staleResult = stale(revision)
      if (staleResult) return staleResult
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'hover', { index })
      if (!res?.success) {
        return {
          ok: false,
          error: { code: 'hover_failed', message: res?.error ?? 'hover failed', recoverable: true },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async drag(fromIndex, toIndex, revision) {
      const staleResult = stale(revision)
      if (staleResult) return staleResult
      const res = await send<{ success: boolean; message?: string; error?: string }>(getTabId(), 'drag', {
        fromIndex,
        toIndex,
      })
      if (!res?.success) {
        return {
          ok: false,
          error: { code: 'drag_failed', message: res?.error ?? 'drag failed', recoverable: true },
        }
      }
      return { ok: true, data: { message: res.message ?? 'ok' } }
    },

    async screenshot() {
      const tabId = getTabId()
      try {
        await Promise.race([
          send<{ success: boolean }>(tabId, 'hide_capture_chrome').catch(() => {}),
          new Promise((resolve) => setTimeout(resolve, 800)),
        ])
        const tab = await chrome.tabs.update(tabId, { active: true })
        if (!tab?.windowId) throw new Error('截图目标标签没有窗口')
        const dataUrl = await captureVisibleTabPng(tab.windowId)
        return { ok: true, data: { dataUrl } }
      } catch (error) {
        const raw = (error as Error).message
        return {
          ok: false,
          error: {
            code: 'screenshot_failed',
            message: friendlyCaptureError(raw),
            recoverable: true,
          },
        }
      } finally {
        await send(tabId, 'restore_capture_chrome').catch(() => {})
      }
    },

    async screenshotFullPage() {
      const tabId = getTabId()
      try {
        await Promise.race([
          send<{ success: boolean }>(tabId, 'hide_capture_chrome').catch(() => {}),
          new Promise((resolve) => setTimeout(resolve, 800)),
        ])
        const tab = await chrome.tabs.get(tabId)
        await chrome.tabs.update(tabId, { active: true })
        const data = await captureFullPageTab(tabId, tab.windowId, send, captureVisibleTabPng)
        return { ok: true, data }
      } catch (error) {
        return {
          ok: false,
          error: {
            code: 'screenshot_full_failed',
            message: friendlyCaptureError((error as Error).message),
            recoverable: true,
          },
        }
      } finally {
        await send(tabId, 'restore_capture_chrome').catch(() => {})
      }
    },

    async toPdf() {
      const tabId = getTabId()
      try {
        await send<{ success: boolean }>(tabId, 'hide_capture_chrome').catch(() => {})
        const tab = await chrome.tabs.get(tabId)
        const dataUrl = await printTabToPdf(tabId)
        return {
          ok: true,
          data: { dataUrl, title: tab.title ?? '', url: tab.url ?? '' },
        }
      } catch (error) {
        return {
          ok: false,
          error: {
            code: 'pdf_failed',
            message: (error as Error).message,
            recoverable: true,
          },
        }
      } finally {
        await send(tabId, 'restore_capture_chrome').catch(() => {})
      }
    },

    async collectPageSignalRaw() {
      const res = await send<{ success: boolean; data?: PageSignalCollectPayload; error?: string }>(
        getTabId(),
        'collect_page_signals',
        {}
      )
      if (!res?.success || !res.data) {
        return {
          ok: false,
          error: {
            code: 'collect_signals_failed',
            message: res?.error ?? 'collect_page_signals failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: res.data }
    },
  }
}
