import { chromium, expect, test, type Page } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')

type PageCall = (action: string, payload?: Record<string, unknown>) => Promise<unknown>

async function withExtension(fn: (args: { page: Page; call: PageCall }) => Promise<void>) {
  const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-scroll-'))
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !!process.env.CI,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  try {
    const page = await context.newPage()
    let sw = context.serviceWorkers()[0]
    if (!sw) sw = await context.waitForEvent('serviceworker')
    const call = (action: string, payload: Record<string, unknown> = {}) =>
      sw.evaluate(
        async ({ action, payload }) => {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
          if (!tab?.id) throw new Error('no active tab')
          return chrome.tabs.sendMessage(tab.id, { type: 'PAGE_CONTROL', action, payload })
        },
        { action, payload }
      )
    await fn({ page, call })
  } finally {
    await context.close()
  }
}

test.describe('scroll + screenshot chrome', () => {
  test.skip(!existsSync(extensionPath), 'run npm run build first')
  test.slow()

  test('scrolls an inner overflow container instead of a no-op window scroll', async ({
    baseURL,
  }) => {
    await withExtension(async ({ page, call }) => {
      await page.setViewportSize({ width: 800, height: 400 })
      await page.goto(`${baseURL ?? ''}/fixtures/inner-scroll.html`)
      await expect(page.locator('#scroller')).toBeVisible()
      const ping = (await call('ping')) as { ok?: boolean }
      expect(ping.ok).toBe(true)
      expect(await page.evaluate(() => document.documentElement.scrollHeight <= window.innerHeight + 1)).toBe(true)

      const before = await page.locator('#scroller').evaluate((el) => el.scrollTop)
      const scrolled = (await call('scroll', { direction: 'down' })) as {
        success: boolean
        target?: string
        delta?: number
        atBottom?: boolean
      }
      expect(scrolled.success).toBe(true)
      expect(scrolled.target).toBe('inner')
      expect(scrolled.delta ?? 0).toBeGreaterThan(8)
      const after = await page.locator('#scroller').evaluate((el) => el.scrollTop)
      expect(after).toBeGreaterThan(before)
    })
  })

  test('hide_capture_chrome hides highlight/mark overlays then restore brings them back', async ({ baseURL }) => {
    await withExtension(async ({ page, call }) => {
      await page.goto(`${baseURL ?? ''}/fixtures/inner-scroll.html`)
      await expect(page.locator('#playwright-highlight-container')).toBeVisible()
      await expect(page.locator('#naviforge-mark-layer')).toBeVisible()

      const hidden = (await call('hide_capture_chrome')) as { success: boolean }
      expect(hidden.success).toBe(true)
      await expect(page.locator('#playwright-highlight-container')).toBeHidden()
      await expect(page.locator('#naviforge-mark-layer')).toBeHidden()

      const restored = (await call('restore_capture_chrome')) as { success: boolean }
      expect(restored.success).toBe(true)
      await expect(page.locator('#playwright-highlight-container')).toBeVisible()
      await expect(page.locator('#naviforge-mark-layer')).toBeVisible()
    })
  })
})
