import { chromium, expect, test, type BrowserContext, type Page } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

import {
  assessExtractedItems,
  classifyEnvironmentBlock,
  type LiveContentItem,
  type LiveSiteCase,
} from './assertions.js'
import { P0_LIVE_SITES, selectedLiveSites } from './sites.js'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')
const liveEnabled = process.env.NAVIFORGE_LIVE === '1'

type ExtractResponse = {
  success: boolean
  marked?: number
  candidates?: number
  items?: LiveContentItem[]
  strategy?: string
  profileId?: string
  shortfall?: string
  error?: string
}

async function launchExtension(site: LiveSiteCase): Promise<{
  context: BrowserContext
  page: Page
  call: (action: string, payload: Record<string, unknown>) => Promise<ExtractResponse>
}> {
  const userDataDir = mkdtempSync(join(tmpdir(), `naviforge-live-${site.id}-`))
  const context = await chromium.launchPersistentContext(userDataDir, {
    // Playwright's headless shell does not reliably start MV3 extension
    // service workers. Nightly runs this headed browser under xvfb.
    headless: false,
    locale: 'zh-CN',
    viewport: { width: 1280, height: 720 },
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const page = context.pages()[0] ?? (await context.newPage())
      await page.goto(site.url, { waitUntil: 'domcontentloaded', timeout: 60_000 })
    await page.bringToFront()
    if (site.waitMs) await page.waitForTimeout(site.waitMs)

    let worker = context.serviceWorkers()[0]
    if (!worker) worker = await context.waitForEvent('serviceworker', { timeout: 15_000 })

    const call = (action: string, payload: Record<string, unknown>) =>
      worker.evaluate(
        async ({ action, payload }) => {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
          if (!tab?.id) throw new Error('no active tab')
          return chrome.tabs.sendMessage(tab.id, {
            type: 'PAGE_CONTROL',
            action,
            payload,
          })
        },
        { action, payload }
      ) as Promise<ExtractResponse>

    return { context, page, call }
  } catch (error) {
    await context.close()
    throw error
  }
}

async function skipIfBlocked(page: Page, site: LiveSiteCase): Promise<void> {
  const evidence = `${await page.title()}\n${(await page.locator('body').innerText()).slice(0, 20_000)}`
  test.skip(
    classifyEnvironmentBlock(evidence) === 'ENV_BLOCKED',
    `ENV_BLOCKED: ${site.name} returned a CAPTCHA, rate limit, region block, or access denial`
  )
}

test.describe('NaviForge P0 live sites', () => {
  test.skip(!liveEnabled, 'set NAVIFORGE_LIVE=1 or use npm run test:live')
  test.skip(!existsSync(extensionPath), 'build the extension before running live tests')

  for (const site of selectedLiveSites()) {
    test(`${site.id}: extract five valid detail records without page marks`, async ({}, testInfo) => {
      const { context, page, call } = await launchExtension(site)
      try {
        await skipIfBlocked(page, site)
        const beforeMarks = await page.locator('[data-naviforge-mark]').count()
        const result = await call('extract_content', { n: site.expected, showHints: false })
        const afterMarks = await page.locator('[data-naviforge-mark]').count()

        await testInfo.attach('extract-report.json', {
          body: JSON.stringify({ site, result }, null, 2),
          contentType: 'application/json',
        })
        expect(result.success, result.error).toBe(true)
        expect(beforeMarks).toBe(0)
        expect(afterMarks).toBe(0)

        const violations = assessExtractedItems(result.items ?? [], site, site.expected)
        if (violations.length) {
          await testInfo.attach('failure.png', {
            body: await page.screenshot({ fullPage: false }),
            contentType: 'image/png',
          })
        }
        expect(violations, JSON.stringify(violations, null, 2)).toEqual([])
      } finally {
        await context.close()
      }
    })
  }

  test('bilibili: “标记top3” produces three accurate, scroll-following marks', async ({}, testInfo) => {
    const site = P0_LIVE_SITES.find((item) => item.id === 'bilibili-knowledge')!
    const { context, page, call } = await launchExtension(site)
    try {
      await skipIfBlocked(page, site)
      const result = await call('mark_topn', { n: 3, showHints: false })
      await testInfo.attach('mark-top3-report.json', {
        body: JSON.stringify({ site, result }, null, 2),
        contentType: 'application/json',
      })

      expect(result.success, result.error).toBe(true)
      expect(result.marked).toBe(3)
      expect(assessExtractedItems(result.items ?? [], site, 3)).toEqual([])
      expect(await page.locator('[data-naviforge-mark]').count()).toBe(3)
      expect(await page.locator('[data-naviforge-overlay]').count()).toBe(3)

      const widths = await page.locator('[data-naviforge-overlay]').evaluateAll((elements) =>
        elements.map((element) => element.getBoundingClientRect().width)
      )
      expect(widths.every((width) => width > 80 && width < 1280 * 0.6)).toBe(true)

      const top1 = page.locator('[data-naviforge-overlay="TOP1"]')
      const beforeScroll = await top1.evaluate((element) => (element as HTMLElement).style.transform)
      await page.evaluate(() => window.scrollBy({ top: 300, behavior: 'instant' }))
      await page.waitForTimeout(150)
      const afterScroll = await top1.evaluate((element) => (element as HTMLElement).style.transform)
      expect(afterScroll).not.toBe(beforeScroll)

      const focused = await call('focus_mark', { label: 'TOP3' })
      expect(focused.success, focused.error).toBe(true)
      await expect(page.locator('[data-naviforge-overlay="TOP3"]')).toHaveAttribute(
        'data-naviforge-focused',
        'true'
      )
    } finally {
      await context.close()
    }
  })
})
