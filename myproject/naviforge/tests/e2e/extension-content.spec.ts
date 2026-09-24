import { chromium, expect, test } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')

test.describe('extension content script', () => {
  test.skip(!existsSync(extensionPath), 'run npm run build first')
  // Each test launches its own persistent Chrome with the unpacked extension.
  test.slow()

  test('ping, snapshot, and execute_js on demo site', async ({ baseURL }) => {
    const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-ext-'))
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: !!process.env.CI,
      args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
    })

    try {
      const page = await context.newPage()
      await page.goto(baseURL ?? '/')

      let sw = context.serviceWorkers()[0]
      if (!sw) sw = await context.waitForEvent('serviceworker')
      const targetTabId = await sw.evaluate(async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (!tab?.id) throw new Error('no active tab')
        return tab.id
      })

      const extensionId = new URL(sw.url()).host
      const extensionPage = await context.newPage()
      await extensionPage.goto(`chrome-extension://${extensionId}/popup.html`)
      const status = await extensionPage.evaluate(async () => {
        await chrome.storage.local.set({
          naviforgeActiveRun: {
            active: true,
            status: 'COMPLETED',
            events: [{ type: 'done', result: 'stale run' }],
          },
        })
        const response = await chrome.runtime.sendMessage({ type: 'AGENT_RUN', action: 'status' })
        const saved = await chrome.storage.local.get('naviforgeActiveRun')
        return { response, saved }
      })
      expect(status.response).toMatchObject({ active: false })
      expect(status.saved.naviforgeActiveRun).toBeUndefined()

      const ping = await sw.evaluate(async (targetTabId) => {
        return chrome.tabs.sendMessage(targetTabId, { type: 'PAGE_CONTROL', action: 'ping' })
      }, targetTabId)
      expect(ping).toMatchObject({ ok: true })

      const snapshot = await sw.evaluate(async (targetTabId) => {
        return chrome.tabs.sendMessage(targetTabId, {
          type: 'PAGE_CONTROL',
          action: 'get_browser_state',
          payload: { showHints: true },
        })
      }, targetTabId)
      expect(snapshot).toMatchObject({ success: true })
      expect((snapshot as { data?: { content?: string } }).data?.content).toBeTruthy()

      const exec = await sw.evaluate(async (targetTabId) => {
        return chrome.tabs.sendMessage(targetTabId, {
          type: 'PAGE_CONTROL',
          action: 'execute_js',
          payload: {
            allowScript: true,
            code: 'return document.querySelectorAll("button").length',
          },
        })
      }, targetTabId)
      expect(exec).toMatchObject({ success: true })
      expect(typeof (exec as { result?: number }).result).toBe('number')
      expect((exec as { result?: number }).result).toBeGreaterThan(0)

      const extracted = await sw.evaluate(async (targetTabId) => {
        return chrome.tabs.sendMessage(targetTabId, {
          type: 'PAGE_CONTROL',
          action: 'extract_dom',
          payload: { kind: 'buttons', limit: 8 },
        })
      }, targetTabId)
      expect(extracted).toMatchObject({ success: true })
      expect((extracted as { data?: { buttons?: unknown[] } }).data?.buttons?.length).toBeGreaterThan(0)

      const hover = await sw.evaluate(async (targetTabId) => {
        return chrome.tabs.sendMessage(targetTabId, {
          type: 'PAGE_CONTROL',
          action: 'hover',
          payload: { index: 1 },
        })
      }, targetTabId)
      expect(hover).toMatchObject({ success: true })
    } finally {
      await context.close()
    }
  })

  test('extract_content reads without marking, mark_items marks on demand', async ({ baseURL }) => {
    const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-ext-'))
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: !!process.env.CI,
      args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
    })

    try {
      const page = await context.newPage()
      await page.setViewportSize({ width: 900, height: 360 })
      await page.goto(`${baseURL ?? ''}/fixtures/video-feed.html`)

      let sw = context.serviceWorkers()[0]
      if (!sw) sw = await context.waitForEvent('serviceworker')

      const call = (action: string, payload: Record<string, unknown>) =>
        sw.evaluate(
          async ({ action, payload }) => {
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
            if (!tab?.id) throw new Error('no active tab')
            return chrome.tabs.sendMessage(tab.id, { type: 'PAGE_CONTROL', action, payload })
          },
          { action, payload }
        )

      const extracted = (await call('extract_content', { n: 4 })) as {
        success: boolean
        items?: Array<{ index: number; title: string; url?: string }>
      }
      expect(extracted.success).toBe(true)
      expect(extracted.items?.map((item) => item.title)).toEqual([
        '三分钟看懂扩散模型',
        '从零实现一个浏览器 Agent',
        'Rust 所有权到底在解决什么问题',
        '一次讲清 HTTP 缓存策略',
      ])

      // The whole point of the split: reading must never mutate the page.
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(0)
      expect(await page.locator('#naviforge-mark-layer').count()).toBe(0)

      const marked = (await call('mark_items', {
        items: extracted.items?.slice(0, 2).map((item, i) => ({
          index: item.index,
          label: `TOP${i + 1}`,
          detail: item.title,
        })),
      })) as { success: boolean; marked?: number }
      expect(marked.success).toBe(true)
      expect(marked.marked).toBe(2)
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(2)

      const focused = (await call('focus_mark', { label: 'TOP2' })) as {
        success: boolean
        focused?: string
      }
      expect(focused).toEqual({ success: true, focused: 'TOP2' })
      await expect(page.locator('[data-naviforge-overlay="TOP2"]')).toHaveAttribute(
        'data-naviforge-focused',
        'true'
      )
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }))
      await page.waitForTimeout(100)
      const beforeScroll = await page
        .locator('[data-naviforge-overlay="TOP2"]')
        .evaluate((element) => (element as HTMLElement).style.transform)
      await page.evaluate(() => window.scrollBy({ top: 120, behavior: 'instant' }))
      await page.waitForTimeout(100)
      const afterScroll = await page
        .locator('[data-naviforge-overlay="TOP2"]')
        .evaluate((element) => (element as HTMLElement).style.transform)
      expect(afterScroll).not.toBe(beforeScroll)

      const top3 = (await call('mark_topn', { n: 3 })) as {
        success: boolean
        marked?: number
        items?: Array<{ label: string; title: string; url?: string }>
      }
      expect(top3.success).toBe(true)
      expect(top3.marked).toBe(3)
      expect(top3.items?.map((item) => item.title)).toEqual([
        '三分钟看懂扩散模型',
        '从零实现一个浏览器 Agent',
        'Rust 所有权到底在解决什么问题',
      ])
      expect(top3.items?.every((item) => item.url?.includes('/video/'))).toBe(true)
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(3)
      expect(await page.locator('[data-naviforge-overlay]').count()).toBe(3)
    } finally {
      await context.close()
    }
  })

  test('extract_content indexes same-origin iframe feeds', async ({ baseURL }) => {
    const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-ext-iframe-'))
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: !!process.env.CI,
      args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
    })

    try {
      const page = await context.newPage()
      await page.goto(`${baseURL ?? ''}/fixtures/iframe-feed.html`)
      await page.waitForLoadState('networkidle')

      let sw = context.serviceWorkers()[0]
      if (!sw) sw = await context.waitForEvent('serviceworker')

      const extracted = (await sw.evaluate(async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (!tab?.id) throw new Error('no active tab')
        return chrome.tabs.sendMessage(tab.id, {
          type: 'PAGE_CONTROL',
          action: 'extract_content',
          payload: { n: 4, showHints: false },
        })
      })) as { success: boolean; items?: Array<{ title: string }> }

      expect(extracted.success).toBe(true)
      expect(extracted.items?.map((item) => item.title)).toEqual([
        'Iframe 视频一',
        'Iframe 视频二',
        'Iframe 视频三',
        'Iframe 视频四',
      ])
    } finally {
      await context.close()
    }
  })

  test('to_markdown and printToPDF on an article page', async ({ baseURL }) => {
    const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-ext-export-'))
    const context = await chromium.launchPersistentContext(userDataDir, {
      headless: !!process.env.CI,
      args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
    })

    try {
      const page = await context.newPage()
      await page.goto(`${baseURL ?? ''}/fixtures/article.html`)

      let sw = context.serviceWorkers()[0]
      if (!sw) sw = await context.waitForEvent('serviceworker')

      const md = (await sw.evaluate(async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (!tab?.id) throw new Error('no active tab')
        return chrome.tabs.sendMessage(tab.id, { type: 'PAGE_CONTROL', action: 'to_markdown' })
      })) as {
        success: boolean
        error?: string
        data?: { markdown: string; title: string; url: string; source: string }
      }
      expect(md.success, md.error).toBe(true)
      expect(md.data?.markdown).toContain('Widget Protocol')
      expect(md.data?.markdown).toMatch(/\*\*JSON\*\*/)
      expect(md.data?.markdown).toContain('Source:')
      expect(md.data?.title).toBeTruthy()

      const printed = (await sw.evaluate(async () => {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (!tab?.id) throw new Error('no active tab')
        const tabId = tab.id
        await chrome.debugger.attach({ tabId }, '1.3')
        try {
          await chrome.debugger.sendCommand({ tabId }, 'Page.enable')
          const result = (await chrome.debugger.sendCommand({ tabId }, 'Page.printToPDF', {
            printBackground: true,
            preferCSSPageSize: true,
            displayHeaderFooter: false,
          })) as { data?: string }
          return { ok: Boolean(result?.data), prefix: result?.data?.slice(0, 8) ?? '' }
        } finally {
          await chrome.debugger.detach({ tabId }).catch(() => {})
        }
      })) as { ok: boolean; prefix: string }
      expect(printed.ok).toBe(true)
      // %PDF base64 starts with JVBERi
      expect(printed.prefix).toBe('JVBERi0x')
    } finally {
      await context.close()
    }
  })
})
