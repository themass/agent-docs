import { chromium, expect, test, type BrowserContext, type Page } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import { assessExtractedItems, classifyEnvironmentBlock } from './assertions.js'
import { P0_LIVE_SITES } from './sites.js'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')
const liveEnabled = process.env.NAVIFORGE_LIVE === '1'
const BILIBILI_URL =
  'https://www.bilibili.com/c/knowledge/?spm_id_from=333.1007.0.0'

type ExtractResponse = {
  success: boolean
  marked?: number
  candidates?: number
  items?: Array<{ title: string; url?: string; index?: number }>
  strategy?: string
  profileId?: string
  shortfall?: string
  error?: string
  data?: {
    feeds?: Array<{ title?: string; href?: string; index?: number }>
    links?: Array<{ href?: string }>
  }
}

async function launchOnBilibili(): Promise<{
  context: BrowserContext
  page: Page
  call: (action: string, payload?: Record<string, unknown>) => Promise<ExtractResponse>
}> {
  const site = P0_LIVE_SITES.find((item) => item.id === 'bilibili-knowledge')!
  const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-bilibili-auto-'))
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: false,
    locale: 'zh-CN',
    viewport: { width: 1280, height: 720 },
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const page = context.pages()[0] ?? (await context.newPage())
    await page.goto(BILIBILI_URL, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    await page.bringToFront()
    await page.waitForTimeout(site.waitMs ?? 5_000)

    let worker = context.serviceWorkers()[0]
    if (!worker) worker = await context.waitForEvent('serviceworker', { timeout: 15_000 })

    const call = (action: string, payload: Record<string, unknown> = {}) =>
      worker.evaluate(
        async ({ action, payload }) => {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
          if (!tab?.id) throw new Error('no active tab')
          return chrome.tabs.sendMessage(tab.id, { type: 'PAGE_CONTROL', action, payload })
        },
        { action, payload }
      ) as Promise<ExtractResponse>

    return { context, page, call }
  } catch (error) {
    await context.close()
    throw error
  }
}

async function skipIfBlocked(page: Page): Promise<void> {
  const evidence = `${await page.title()}\n${(await page.locator('body').innerText()).slice(0, 20_000)}`
  test.skip(
    classifyEnvironmentBlock(evidence) === 'ENV_BLOCKED',
    'ENV_BLOCKED: bilibili returned CAPTCHA, rate limit, or region block'
  )
}

function overlapCount(a: string[], b: string[]): number {
  const setB = new Set(b)
  return a.filter((url) => setB.has(url)).length
}

async function markOverlayAligned(page: Page, label: string): Promise<boolean> {
  return page.evaluate((markLabel) => {
    const anchor = document.querySelector(`[data-naviforge-mark="${markLabel}"]`)
    const overlay = document.querySelector(`[data-naviforge-overlay="${markLabel}"]`)
    if (!(anchor instanceof HTMLElement) || !(overlay instanceof HTMLElement)) return false
    const rect = anchor.getBoundingClientRect()
    const match = overlay.style.transform.match(/translate\(([-\d.]+)px,\s*([-\d.]+)px\)/)
    if (!match) return false
    const ox = Number(match[1])
    const oy = Number(match[2])
    return Math.abs(ox - Math.max(0, rect.left - 4)) < 3 && Math.abs(oy - Math.max(0, rect.top - 4)) < 3
  }, label)
}

test.describe('Bilibili knowledge automation', () => {
  test.skip(!liveEnabled, 'set NAVIFORGE_LIVE=1')
  test.skip(!existsSync(extensionPath), 'build the extension before running live tests')

  test('case1: extract top4, scroll, re-extract fresh viewport items', async ({}, testInfo) => {
    const site = P0_LIVE_SITES.find((item) => item.id === 'bilibili-knowledge')!
    const { context, page, call } = await launchOnBilibili()
    try {
      await skipIfBlocked(page)
      const beforeMarks = await page.locator('[data-naviforge-mark]').count()
      const first = await call('extract_content', { n: 4, showHints: false })
      await testInfo.attach('case1-first-extract.json', {
        body: JSON.stringify(first, null, 2),
        contentType: 'application/json',
      })

      expect(first.success, first.error).toBe(true)
      expect(beforeMarks).toBe(0)
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(0)
      expect(assessExtractedItems(first.items ?? [], site, 4)).toEqual([])

      const urlsBefore = (first.items ?? []).map((item) => item.url!).filter(Boolean)
      await page.evaluate(() => window.scrollBy({ top: 900, behavior: 'instant' }))
      await page.waitForTimeout(800)

      const second = await call('extract_content', { n: 4, showHints: false })
      await testInfo.attach('case1-after-scroll-extract.json', {
        body: JSON.stringify(second, null, 2),
        contentType: 'application/json',
      })
      expect(second.success, second.error).toBe(true)
      expect(assessExtractedItems(second.items ?? [], site, 4)).toEqual([])

      const urlsAfter = (second.items ?? []).map((item) => item.url!).filter(Boolean)
      const overlap = overlapCount(urlsBefore, urlsAfter)
      expect(overlap, `expected scroll to change viewport records, overlap=${overlap}`).toBeLessThan(4)
    } finally {
      await context.close()
    }
  })

  test('case2: mark top3, scroll, marks follow and re-mark succeeds', async ({}, testInfo) => {
    const site = P0_LIVE_SITES.find((item) => item.id === 'bilibili-knowledge')!
    const { context, page, call } = await launchOnBilibili()
    try {
      await skipIfBlocked(page)
      const first = await call('mark_topn', { n: 3, showHints: false })
      await testInfo.attach('case2-first-mark.json', {
        body: JSON.stringify(first, null, 2),
        contentType: 'application/json',
      })
      expect(first.success, first.error).toBe(true)
      expect(first.marked).toBe(3)
      expect(assessExtractedItems(first.items ?? [], site, 3)).toEqual([])
      expect(await page.locator('[data-naviforge-overlay]').count()).toBe(3)

      await page.evaluate(() => window.scrollBy({ top: 900, behavior: 'instant' }))
      await page.waitForTimeout(800)

      const remark = await call('mark_topn', { n: 3, showHints: false })
      await testInfo.attach('case2-after-scroll-remark.json', {
        body: JSON.stringify(remark, null, 2),
        contentType: 'application/json',
      })
      expect(remark.success, remark.error).toBe(true)
      expect(remark.marked).toBe(3)
      expect(assessExtractedItems(remark.items ?? [], site, 3)).toEqual([])
      expect(await page.locator('[data-naviforge-overlay]').count()).toBe(3)

      const urlsFirst = (first.items ?? []).map((item) => item.url).filter(Boolean) as string[]
      const urlsRemark = (remark.items ?? []).map((item) => item.url).filter(Boolean) as string[]
      expect(overlapCount(urlsFirst, urlsRemark)).toBeLessThan(3)
    } finally {
      await context.close()
    }
  })

  test('case3: extract_dom feeds exposes video list structure for scripting', async ({}, testInfo) => {
    const { context, page, call } = await launchOnBilibili()
    try {
      await skipIfBlocked(page)
      const dom = await call('extract_dom', { kind: 'feeds', limit: 24 })
      await testInfo.attach('case3-extract-dom.json', {
        body: JSON.stringify(dom, null, 2),
        contentType: 'application/json',
      })
      expect(dom.success).toBe(true)
      const feeds = dom.data?.feeds ?? []
      expect(feeds.length).toBeGreaterThanOrEqual(4)
      const videoFeeds = feeds.filter((item) => item.href?.includes('/video/'))
      expect(videoFeeds.length).toBeGreaterThanOrEqual(4)
      expect(videoFeeds.filter((item) => (item.title ?? '').trim().length > 0).length).toBeGreaterThanOrEqual(4)
    } finally {
      await context.close()
    }
  })

  test('case4: extract is side-effect free; focus_mark locates TOP3', async ({}, testInfo) => {
    const { context, page, call } = await launchOnBilibili()
    try {
      await skipIfBlocked(page)
      const extract = await call('extract_content', { n: 5, showHints: false })
      expect(extract.success, extract.error).toBe(true)
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(0)
      expect(await page.locator('[data-naviforge-overlay]').count()).toBe(0)

      const mark = await call('mark_topn', { n: 3, showHints: false })
      expect(mark.success, mark.error).toBe(true)
      const focused = await call('focus_mark', { label: 'TOP3' })
      expect(focused.success, focused.error).toBe(true)
      await expect(page.locator('[data-naviforge-overlay="TOP3"]')).toHaveAttribute(
        'data-naviforge-focused',
        'true'
      )

      await testInfo.attach('case4-focus-top3.png', {
        body: await page.screenshot({ fullPage: false }),
        contentType: 'image/png',
      })
    } finally {
      await context.close()
    }
  })

  test('case5: repeated extract without scroll is stable (no duplicate drift)', async ({}, testInfo) => {
    const site = P0_LIVE_SITES.find((item) => item.id === 'bilibili-knowledge')!
    const { context, page, call } = await launchOnBilibili()
    try {
      await skipIfBlocked(page)
      const a = await call('extract_content', { n: 4, showHints: false })
      const b = await call('extract_content', { n: 4, showHints: false })
      await testInfo.attach('case5-repeat-extract.json', {
        body: JSON.stringify({ a, b }, null, 2),
        contentType: 'application/json',
      })
      expect(a.success, a.error).toBe(true)
      expect(b.success, b.error).toBe(true)
      expect(assessExtractedItems(a.items ?? [], site, 4)).toEqual([])
      expect(assessExtractedItems(b.items ?? [], site, 4)).toEqual([])
      const urlsA = (a.items ?? []).map((item) => item.url)
      const urlsB = (b.items ?? []).map((item) => item.url)
      expect(urlsB).toEqual(urlsA)
    } finally {
      await context.close()
    }
  })
})
