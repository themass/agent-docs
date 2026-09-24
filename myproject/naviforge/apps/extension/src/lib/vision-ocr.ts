import { ocrImage } from '@naviforge/runtime'

import {
  getActiveModelProfile,
  getOcrModelProfile,
  isBlockedOcrModel,
  loadModelProfiles,
  profileToLlmConfig,
  type ModelProfile,
} from './llm-profiles'
import { loadNewApiAuth } from './newapi-auth'
import { syncManagedProfilesFromNewApi } from './newapi-sync'
import { toolkitScreenshot } from './toolkit-actions'
import {
  blockedOcrModelHint,
  clampPixelCrop,
  confirmOcrUpload,
  cssRectToPixels,
  formatOcrError,
  formatOcrMarkdown,
  MIN_CROP_CSS_PX,
  type CssRect,
} from './vision-ocr-core'

export {
  blockedOcrModelHint,
  clampPixelCrop,
  confirmOcrUpload,
  cssRectToPixels,
  formatOcrError,
  formatOcrMarkdown,
  isBrowserPdfUrl,
  MIN_CROP_CSS_PX,
  type CssRect,
} from './vision-ocr-core'

const MAX_EDGE = 2048
const JPEG_QUALITY = 0.82
const WEBP_QUALITY = 0.82
const MAX_DATA_URL_CHARS = 1_400_000

function canvasToVisionDataUrl(canvas: HTMLCanvasElement): string {
  const webp = canvas.toDataURL('image/webp', WEBP_QUALITY)
  if (webp.startsWith('data:image/webp')) {
    if (webp.length <= MAX_DATA_URL_CHARS) return webp
    const smallerWebp = canvas.toDataURL('image/webp', 0.7)
    if (smallerWebp.length <= MAX_DATA_URL_CHARS) return smallerWebp
  }
  let jpeg = canvas.toDataURL('image/jpeg', JPEG_QUALITY)
  if (jpeg.length > MAX_DATA_URL_CHARS) jpeg = canvas.toDataURL('image/jpeg', 0.7)
  return jpeg
}

type CropRegionResponse = {
  success: boolean
  cancelled?: boolean
  rect?: CssRect
  devicePixelRatio?: number
  error?: string
}

async function sendCropRegion(tabId: number): Promise<CropRegionResponse> {
  const message = { type: 'PAGE_CONTROL', action: 'crop_region', targetTabId: tabId }
  try {
    return (await chrome.tabs.sendMessage(tabId, message)) as CropRegionResponse
  } catch {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content-scripts/content.js'],
    })
    return (await chrome.tabs.sendMessage(tabId, message)) as CropRegionResponse
  }
}

async function blobToDataUrl(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]!)
  return `data:${blob.type};base64,${btoa(binary)}`
}

async function bitmapRegionToDataUrl(
  bitmap: ImageBitmap,
  crop: { x: number; y: number; width: number; height: number },
  maxEdge: number
): Promise<string> {
  const scale = Math.min(1, maxEdge / Math.max(crop.width, crop.height))
  const width = Math.max(1, Math.round(crop.width * scale))
  const height = Math.max(1, Math.round(crop.height * scale))

  if (typeof OffscreenCanvas !== 'undefined') {
    const canvas = new OffscreenCanvas(width, height)
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法裁切截图')
    ctx.drawImage(bitmap, crop.x, crop.y, crop.width, crop.height, 0, 0, width, height)
    const webp = await canvas.convertToBlob({ type: 'image/webp', quality: WEBP_QUALITY })
    const webpUrl = await blobToDataUrl(webp)
    if (webpUrl.length <= MAX_DATA_URL_CHARS) return webpUrl
    const jpeg = await canvas.convertToBlob({ type: 'image/jpeg', quality: JPEG_QUALITY })
    return blobToDataUrl(jpeg)
  }

  if (typeof document === 'undefined') {
    throw new Error('当前环境无法裁切截图，请从侧栏或工具页重试')
  }
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法裁切截图')
  ctx.drawImage(bitmap, crop.x, crop.y, crop.width, crop.height, 0, 0, width, height)
  return canvasToVisionDataUrl(canvas)
}

export async function cropToJpeg(
  dataUrl: string,
  cssRect: CssRect,
  dpr: number,
  maxEdge = MAX_EDGE
): Promise<string> {
  const blob = await (await fetch(dataUrl)).blob()
  const bitmap = await createImageBitmap(blob)
  try {
    const crop = clampPixelCrop(cssRectToPixels(cssRect, dpr), bitmap.width, bitmap.height)
    if (crop.width < MIN_CROP_CSS_PX || crop.height < MIN_CROP_CSS_PX) {
      throw new Error('选区太小，请再拖一次')
    }
    return await bitmapRegionToDataUrl(bitmap, crop, maxEdge)
  } finally {
    bitmap.close()
  }
}

function isLlmNotFound(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /HTTP 404|bad_response_status_code|not found/i.test(message)
}

/** OCR profile + optional chat fallback when managed OCR model is missing on gateway. */
export async function prepareOcrProfiles(): Promise<{
  profile: ModelProfile
  fallbackProfile?: ModelProfile
}> {
  const auth = await loadNewApiAuth()
  if (auth.mode === 'managed') {
    await syncManagedProfilesFromNewApi()
  }
  const store = await loadModelProfiles()
  const profile = getOcrModelProfile(store)
  if (!profile) {
    throw new Error('还没选 OCR / 视觉模型。打开控制台 → 模型，选千问 OCR 或豆包 vision，不要用 DeepSeek V4。')
  }
  if (!profile.apiKey.trim()) throw new Error(`OCR 模型「${profile.name}」没有 API Key`)
  if (isBlockedOcrModel(profile.model)) throw new Error(blockedOcrModelHint(profile.model))

  let fallbackProfile: ModelProfile | undefined
  if (auth.mode === 'managed') {
    const chat = getActiveModelProfile(store)
    if (chat.id !== profile.id && !isBlockedOcrModel(chat.model) && chat.apiKey.trim()) {
      fallbackProfile = chat
    }
  }
  return { profile, fallbackProfile }
}

async function runOcrWithProfile(profile: ModelProfile, imageDataUrl: string): Promise<string> {
  const result = await ocrImage({ llm: profileToLlmConfig(profile), imageDataUrl })
  return result.text
}

export async function runOcrImage(imageDataUrl: string): Promise<string> {
  const { profile, fallbackProfile } = await prepareOcrProfiles()
  try {
    return await runOcrWithProfile(profile, imageDataUrl)
  } catch (error) {
    if (fallbackProfile && isLlmNotFound(error)) {
      return runOcrWithProfile(fallbackProfile, imageDataUrl)
    }
    throw error
  }
}

async function sendOcrHud(
  tabId: number,
  payload: { phase: 'working' | 'result' | 'error'; text?: string; path?: string }
): Promise<void> {
  const message = { type: 'PAGE_CONTROL', action: 'ocr_hud', payload, targetTabId: tabId }
  try {
    await chrome.tabs.sendMessage(tabId, message)
  } catch {
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['content-scripts/content.js'],
      })
      await chrome.tabs.sendMessage(tabId, message)
    } catch {
      // restricted page
    }
  }
}

export async function runToolkitOcr(tab: chrome.tabs.Tab): Promise<{ cancelled: true } | { text: string; path?: string }> {
  if (!tab.id) throw new Error('请先选择要识别的网页')
  const { profile } = await prepareOcrProfiles()
  if (!(await confirmOcrUpload(profile.name, tab.id))) return { cancelled: true }

  await chrome.tabs.update(tab.id, { active: true })
  if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })

  const cropped = await sendCropRegion(tab.id)
  if (cropped.cancelled) return { cancelled: true }
  if (!cropped.success || !cropped.rect) throw new Error(cropped.error ?? '框选失败')

  // Overlay is gone; wait one frame so captureVisibleTab does not include it.
  await new Promise((resolve) => setTimeout(resolve, 50))
  const shot = await toolkitScreenshot(tab.id)
  if (!shot.ok || !shot.data?.dataUrl) {
    throw new Error(!shot.ok ? shot.error.message : '截图失败')
  }
  await sendOcrHud(tab.id, { phase: 'working' })
  const imageDataUrl = await cropToJpeg(shot.data.dataUrl, cropped.rect, cropped.devicePixelRatio ?? 1)
  try {
    const text = await runOcrImage(imageDataUrl)
    const path = await persistOcrText(text, tab.url)
    await sendOcrHud(tab.id, { phase: 'result', text, path })
    return { text, path }
  } catch (error) {
    const message = formatOcrError(error)
    await sendOcrHud(tab.id, { phase: 'error', text: message })
    throw new Error(message)
  }
}

async function persistOcrText(text: string, sourceUrl?: string): Promise<string | undefined> {
  const markdown = formatOcrMarkdown(text, sourceUrl)
  const { downloadFallback, saveWorkspacePage } = await import('./local-workspace')
  const saved = await saveWorkspacePage({ kind: 'md', slug: 'ocr', content: markdown })
  if (saved?.relativePath) return saved.relativePath
  try {
    const filename = `pages/naviforge-ocr-${Date.now()}.md`
    await downloadFallback(
      `data:text/markdown;charset=utf-8,${encodeURIComponent(markdown)}`,
      filename
    )
    return `Downloads/NaviForge/${filename}`
  } catch {
    return undefined
  }
}

export async function compressVisionImage(dataUrl: string, maxEdge = MAX_EDGE): Promise<string> {
  const blob = await (await fetch(dataUrl)).blob()
  const bitmap = await createImageBitmap(blob)
  try {
    const crop = { x: 0, y: 0, width: bitmap.width, height: bitmap.height }
    return await bitmapRegionToDataUrl(bitmap, crop, maxEdge)
  } finally {
    bitmap.close()
  }
}

/** @deprecated Use {@link compressVisionImage} (WebP preferred). */
export async function compressDataUrlJpeg(dataUrl: string, maxEdge = MAX_EDGE): Promise<string> {
  return compressVisionImage(dataUrl, maxEdge)
}

/**
 * Full visible-viewport OCR (no crop). Used when Agent hits a Chrome PDF viewer
 * that has no readable DOM.
 */
export async function ocrVisiblePage(tab: chrome.tabs.Tab): Promise<{ text: string }> {
  if (!tab.id) throw new Error('请先选择要识别的网页')
  const { profile } = await prepareOcrProfiles()
  if (!(await confirmOcrUpload(profile.name, tab.id))) {
    throw new Error('需要先确认将截图发给 OCR 模型（Toolkit「识别文字」也会弹出同一确认）')
  }
  await chrome.tabs.update(tab.id, { active: true })
  if (tab.windowId != null) await chrome.windows.update(tab.windowId, { focused: true })
  const shot = await toolkitScreenshot(tab.id)
  if (!shot.ok || !shot.data?.dataUrl) {
    throw new Error(!shot.ok ? shot.error.message : '截图失败')
  }
  const imageDataUrl = await compressVisionImage(shot.data.dataUrl)
  try {
    const text = await runOcrImage(imageDataUrl)
    return { text }
  } catch (error) {
    throw new Error(formatOcrError(error))
  }
}
