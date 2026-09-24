import { chromium, expect, test, type BrowserContext, type Page } from '@playwright/test'
import { existsSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const extensionPath = resolve(import.meta.dirname, '../../apps/extension/dist/chrome-mv3')

async function launchExtension(): Promise<{
  context: BrowserContext
  extensionId: string
}> {
  const userDataDir = mkdtempSync(join(tmpdir(), 'naviforge-media-'))
  const context = await chromium.launchPersistentContext(userDataDir, {
    // Same as extension-content.spec: headed locally; CI uses Chromium headless.
    headless: !!process.env.CI,
    args: [
      `--disable-extensions-except=${extensionPath}`,
      `--load-extension=${extensionPath}`,
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream',
    ],
  })
  if (!context.pages().length) await context.newPage()
  let sw = context.serviceWorkers()[0]
  if (!sw) sw = await context.waitForEvent('serviceworker', { timeout: 20_000 })
  return { context, extensionId: new URL(sw.url()).host }
}

async function openExtensionPage(
  context: BrowserContext,
  extensionId: string,
  file: 'workspace.html' | 'sidepanel.html',
): Promise<Page> {
  const page = await context.newPage()
  await page.addInitScript(() => {
    const g = globalThis as typeof globalThis & {
      __naviforgeGum?: number
      __naviforgeSr?: { ctor: string; starts: number }
    }
    g.__naviforgeGum = 0
    const media = navigator.mediaDevices
    if (media?.getUserMedia) {
      const orig = media.getUserMedia.bind(media)
      media.getUserMedia = async (constraints) => {
        g.__naviforgeGum = (g.__naviforgeGum ?? 0) + 1
        return orig(constraints)
      }
    }
    const recGlobal = globalThis as typeof globalThis & {
      SpeechRecognition?: new () => { start: () => void }
      webkitSpeechRecognition?: new () => { start: () => void }
    }
    const Orig = recGlobal.SpeechRecognition ?? recGlobal.webkitSpeechRecognition
    g.__naviforgeSr = { ctor: Orig ? 'present' : 'missing', starts: 0 }
    if (!Orig) return
    const Wrap = function Wrap() {
      const rec = new Orig()
      const start = rec.start.bind(rec)
      rec.start = () => {
        g.__naviforgeSr!.starts += 1
        return start()
      }
      return rec
    } as unknown as new () => { start: () => void }
    recGlobal.SpeechRecognition = Wrap
    recGlobal.webkitSpeechRecognition = Wrap
  })
  await page.goto(`chrome-extension://${extensionId}/${file}`)
  return page
}

test.describe('composer camera and mic', () => {
  test.skip(!existsSync(extensionPath), 'run npm run build first')
  test.slow()

  test('camera is preview-then-shutter, never auto-captures', async () => {
    const { context, extensionId } = await launchExtension()
    try {
      const page = await openExtensionPage(context, extensionId, 'workspace.html')
      await page.getByRole('button', { name: '添加' }).click()
      await page.getByRole('button', { name: '摄像头拍照' }).click()
      await expect(page.getByRole('dialog', { name: '摄像头' })).toBeVisible()
      await expect(page.getByRole('button', { name: '拍照' })).toBeEnabled({ timeout: 15_000 })
      expect(await page.evaluate(() => (globalThis as { __naviforgeGum?: number }).__naviforgeGum)).toBe(1)

      await page.getByRole('button', { name: '拍照' }).click()
      await expect(page.getByRole('button', { name: '使用这张' })).toBeVisible()
      await expect(page.getByRole('img', { name: '即将使用的照片' })).toBeVisible()

      await page.getByRole('button', { name: '使用这张' }).click()
      await expect(page.getByText('摄像头', { exact: true }).nth(0)).toBeVisible()
      await expect(page.locator('img[src^="data:image/jpeg"]')).toBeVisible()
    } finally {
      await context.close()
    }
  })

  test('side panel shutter stays on screen', async () => {
    const { context, extensionId } = await launchExtension()
    try {
      const page = await openExtensionPage(context, extensionId, 'sidepanel.html')
      await page.setViewportSize({ width: 380, height: 640 })
      await page.getByRole('button', { name: '添加' }).click()
      await page.getByRole('button', { name: '摄像头拍照' }).click()
      const shutter = page.getByRole('button', { name: '拍照' })
      await expect(shutter).toBeEnabled({ timeout: 15_000 })
      await expect(shutter).toBeInViewport()
    } finally {
      await context.close()
    }
  })

  test('mic click does not restart-loop on speech errors', async () => {
    const { context, extensionId } = await launchExtension()
    try {
      const page = await openExtensionPage(context, extensionId, 'workspace.html')
      const mic = page.getByTitle('按住说话 · 点一下持续听')
      await expect(mic).toBeVisible()

      const before = await page.evaluate(
        () => (globalThis as { __naviforgeSr?: { ctor: string; starts: number } }).__naviforgeSr,
      )
      await mic.click()
      await page.waitForTimeout(1500)
      const after = await page.evaluate(
        () => (globalThis as { __naviforgeSr?: { ctor: string; starts: number } }).__naviforgeSr,
      )
      expect(after?.ctor).toBe(before?.ctor)
      if (after?.ctor === 'missing') {
        await expect(page.getByText('这个浏览器不支持语音识别，请用 Chrome')).toBeVisible()
        return
      }
      expect(after?.starts ?? 0).toBeGreaterThanOrEqual(1)
      expect(after?.starts ?? 0).toBeLessThan(5)
    } finally {
      await context.close()
    }
  })
})
