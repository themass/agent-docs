import { chromium, expect, test, type BrowserContext, type Page, type Worker } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')

async function launchExtension(): Promise<{
  context: BrowserContext
  extensionId: string
  sw: Worker
}> {
  const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-toolkit-'))
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !!process.env.CI,
    args: [`--disable-extensions-except=${extensionPath}`, `--load-extension=${extensionPath}`],
  })
  if (!context.pages().length) await context.newPage()
  let sw = context.serviceWorkers()[0]
  if (!sw) sw = await context.waitForEvent('serviceworker', { timeout: 20_000 })
  return { context, extensionId: new URL(sw.url()).host, sw }
}

async function openDemoTab(
  context: BrowserContext,
  sw: Worker,
  url: string
): Promise<{ page: Page; tabId: number }> {
  const page = await context.newPage()
  await page.goto(url)
  await page.bringToFront()
  const tabId = await sw.evaluate(async (match) => {
    const tabs = await chrome.tabs.query({})
    const tab = tabs.find((item) => item.url === match)
    if (!tab?.id) throw new Error(`no tab for ${match}`)
    return tab.id
  }, page.url())
  await expect
    .poll(async () => {
      try {
        return await sw.evaluate(
          async (id) => chrome.tabs.sendMessage(id, { type: 'PAGE_CONTROL', action: 'ping' }),
          tabId
        )
      } catch {
        return { ok: false }
      }
    })
    .toMatchObject({ ok: true })
  await sw.evaluate(async (id) => {
    await chrome.storage.local.set({ naviforgeToolkitTabId: id })
  }, tabId)
  for (const extra of context.pages()) {
    if (extra !== page && extra.url().startsWith('about:')) await extra.close()
  }
  return { page, tabId }
}

async function bindToolkitTarget(options: Page, title: RegExp): Promise<void> {
  const bound = options.locator('.toolkit-bound-card')
  if (await bound.isVisible()) return
  const recent = options.getByRole('button', { name: '选最近打开的网页' })
  if (await recent.isVisible()) {
    await recent.click()
    try {
      await expect(bound).toBeVisible({ timeout: 5_000 })
      return
    } catch {
      // picker fallback
    }
  }
  const pick = options.getByRole('button', { name: '选择网页…' })
  if (await pick.isVisible()) await pick.click()
  await options.locator('button.toolkit-tab-option').filter({ hasText: title }).first().click()
  await expect(bound).toBeVisible({ timeout: 15_000 })
}

test.describe('toolkit surface feedback', () => {
  test.skip(!existsSync(extensionPath), 'run npm run build first')
  test.slow()

  test('translate HUD appears on the target page before GTX finishes', async ({ baseURL }) => {
    const { context, extensionId, sw } = await launchExtension()
    try {
      const article = `${baseURL ?? 'http://127.0.0.1:4177'}/fixtures/article.html`
      const { page } = await openDemoTab(context, sw, article)
      const options = await context.newPage()
      await options.goto(`chrome-extension://${extensionId}/options.html#toolkit`)
      await expect(options.getByRole('heading', { name: '点「运行」执行工具' })).toBeVisible({ timeout: 20_000 })
      await bindToolkitTarget(options, /Export Article|article\.html|Widget Protocol/)
      const row = options.locator('article.data-list-row').filter({
        has: options.locator('strong', { hasText: '翻译页面' }),
      })
      await expect(row.getByRole('button', { name: '运行' })).toBeEnabled({ timeout: 15_000 })
      await row.getByRole('button', { name: '运行' }).click()
      await expect(page.locator('#naviforge-translate-hud')).toBeVisible({ timeout: 15_000 })
      await expect(page.locator('#naviforge-translate-hud')).toContainText(/正在.*译|已译成|翻译失败|已还原/)
    } finally {
      await context.close()
    }
  })

  test('OCR crop overlay accepts a drag without calling the vision model', async ({ baseURL }) => {
    const { context, sw } = await launchExtension()
    try {
      const article = `${baseURL ?? 'http://127.0.0.1:4177'}/fixtures/article.html`
      const { page, tabId } = await openDemoTab(context, sw, article)
      const cropPromise = sw.evaluate(
        async (id) => chrome.tabs.sendMessage(id, { type: 'PAGE_CONTROL', action: 'crop_region' }),
        tabId
      )
      const overlay = page.locator('[data-naviforge-crop]')
      await expect(overlay).toBeVisible({ timeout: 10_000 })
      const box = await overlay.boundingBox()
      if (!box) throw new Error('crop overlay has no box')
      await page.mouse.move(box.x + 40, box.y + 40)
      await page.mouse.down()
      await page.mouse.move(box.x + 220, box.y + 180, { steps: 8 })
      await page.mouse.up()
      const cropped = (await cropPromise) as {
        success?: boolean
        rect?: { width: number; height: number }
      }
      expect(cropped.success).toBe(true)
      expect(cropped.rect?.width ?? 0).toBeGreaterThanOrEqual(8)
      expect(cropped.rect?.height ?? 0).toBeGreaterThanOrEqual(8)
    } finally {
      await context.close()
    }
  })

  test('visible capture writes workspace notice even if Host save fails', async ({ baseURL }) => {
    const { context, extensionId, sw } = await launchExtension()
    try {
      const article = `${baseURL ?? 'http://127.0.0.1:4177'}/fixtures/article.html`
      const { page, tabId } = await openDemoTab(context, sw, article)
      const options = await context.newPage()
      await options.goto(`chrome-extension://${extensionId}/options.html#workspace`)
      const result = await options.evaluate(async (id) => {
        return chrome.runtime.sendMessage({
          type: 'TOOLKIT_CAPTURE',
          kind: 'visible',
          tabId: id,
        }) as Promise<{
          ok?: boolean
          started?: boolean
          error?: string
          path?: string
        }>
      }, tabId)
      expect(result).toMatchObject({ ok: true, started: true })
      await expect(page.locator('#naviforge-toolkit-toast')).toBeVisible({ timeout: 15_000 })
      await expect(page.locator('#naviforge-toolkit-toast')).toContainText(/截图已保存|已保存/)
      await expect(page.locator('#naviforge-toolkit-toast')).toContainText(/shots\/|Downloads\//)
      await expect(page.locator('#naviforge-toolkit-toast')).not.toContainText(/activeTab/)
      await expect(options.locator('.notice')).toBeVisible({ timeout: 10_000 })
      await expect(options.locator('.notice')).not.toContainText(/activeTab/)
    } finally {
      await context.close()
    }
  })
})
