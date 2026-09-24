import { resolveToolkitTab, toolkitScreenshot } from '../../../lib/toolkit-actions.js'
import type { CssRect } from '../../../lib/vision-ocr-core.js'
import { STUDIO_REGION_HINT } from '../messages.js'
import { writeStudioSession } from '../session.js'
import { cropDataUrlPng } from './crop-png.js'
import { sendPageControl } from './page-control.js'

type CropRegionResponse = {
  success: boolean
  cancelled?: boolean
  rect?: CssRect
  devicePixelRatio?: number
  error?: string
}

let launchInFlight = false

export async function launchScreenshotStudio(
  tabId?: number
): Promise<{ ok: boolean; cancelled?: boolean; error?: string }> {
  if (launchInFlight) return { ok: false, error: '正在处理截图，请稍候' }
  launchInFlight = true
  try {
    const tab = await resolveToolkitTab(tabId)
    if (!tab?.id) return { ok: false, error: '没有可截图的网页标签，请先打开目标页面' }

    await chrome.tabs.update(tab.id, { active: true })
    if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })

    await sendPageControl(tab.id, 'hide_capture_chrome', {})
    const cropped = await sendPageControl<CropRegionResponse>(tab.id, 'crop_region', {
      hint: STUDIO_REGION_HINT,
    })

    if (cropped.cancelled) {
      await sendPageControl(tab.id, 'restore_capture_chrome', {})
      return { ok: true, cancelled: true }
    }
    if (!cropped.success || !cropped.rect) {
      await sendPageControl(tab.id, 'restore_capture_chrome', {})
      return { ok: false, error: cropped.error ?? '框选失败' }
    }

    await new Promise((resolve) => setTimeout(resolve, 50))
    const shot = await toolkitScreenshot(tab.id)
    await sendPageControl(tab.id, 'restore_capture_chrome', {})

    if (!shot.ok || !shot.data?.dataUrl) {
      return { ok: false, error: !shot.ok ? shot.error.message : '截图失败' }
    }

    const baseImageDataUrl = await cropDataUrlPng(
      shot.data.dataUrl,
      cropped.rect,
      cropped.devicePixelRatio ?? 1
    )
    const session = await writeStudioSession({
      baseImageDataUrl,
      sourceTabId: tab.id,
      sourceWindowId: tab.windowId,
      sourceUrl: tab.url,
      annotations: [],
    })

    const url = new URL(chrome.runtime.getURL('screenshot-studio.html'))
    url.searchParams.set('id', session.id)
    await chrome.tabs.create({ url: url.toString() })
    return { ok: true }
  } catch (error) {
    return { ok: false, error: (error as Error).message }
  } finally {
    launchInFlight = false
  }
}
