import { STORAGE } from './settings'

export type CssRect = { x: number; y: number; width: number; height: number }

export const MIN_CROP_CSS_PX = 8

export function blockedOcrModelHint(model: string): string {
  return `当前 OCR 模型「${model}」不能看图。请在控制台 → 模型把 OCR / 视觉模型换成 qwen3.5-ocr、豆包 vision 或 Claude Sonnet。`
}

export function cssRectToPixels(rect: CssRect, dpr: number): CssRect {
  const scale = Number.isFinite(dpr) && dpr > 0 ? dpr : 1
  return {
    x: Math.round(rect.x * scale),
    y: Math.round(rect.y * scale),
    width: Math.round(rect.width * scale),
    height: Math.round(rect.height * scale),
  }
}

export function clampPixelCrop(rect: CssRect, imageWidth: number, imageHeight: number): CssRect {
  const x = Math.min(imageWidth, Math.max(0, rect.x))
  const y = Math.min(imageHeight, Math.max(0, rect.y))
  return {
    x,
    y,
    width: Math.min(imageWidth - x, Math.max(0, rect.width)),
    height: Math.min(imageHeight - y, Math.max(0, rect.height)),
  }
}

export function formatOcrMarkdown(text: string, sourceUrl?: string): string {
  const lines = ['# OCR']
  if (sourceUrl) lines.push('', `Source: ${sourceUrl}`)
  lines.push('', text.trim(), '')
  return lines.join('\n')
}

export function formatOcrError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error)
  if (/HTTP 400/.test(message) && /image|vision|multimodal|content|unsupported/i.test(message)) {
    return '当前 OCR 模型不接受图片，请换成 qwen3.5-ocr、豆包 vision 或 Claude Sonnet'
  }
  return message
}

/** OCR upload consent — works in extension pages and service worker (via tab confirm). */
export async function confirmOcrUpload(profileName: string, tabId?: number): Promise<boolean> {
  const saved = await chrome.storage.local.get(STORAGE.ocrUploadConfirmed)
  if (saved[STORAGE.ocrUploadConfirmed] === true) return true

  const prompt = `将把选区截图发给 OCR 模型「${profileName}」进行识别。是否继续？`
  let ok = false

  if (typeof globalThis.confirm === 'function') {
    ok = globalThis.confirm(prompt)
  } else if (tabId != null) {
    try {
      const [injected] = await chrome.scripting.executeScript({
        target: { tabId },
        func: (text: string) => confirm(text),
        args: [prompt],
      })
      ok = Boolean(injected?.result)
    } catch {
      throw new Error('无法在此页面弹出 OCR 确认框，请换普通 http(s) 网页后重试')
    }
  } else {
    throw new Error('请先打开普通网页后再运行 OCR')
  }

  if (ok) await chrome.storage.local.set({ [STORAGE.ocrUploadConfirmed]: true })
  return ok
}

/** Chrome PDF viewer / direct .pdf URL — DOM snapshot is empty; use visible OCR. */
export function isBrowserPdfUrl(url?: string): boolean {
  if (!url) return false
  try {
    const parsed = new URL(url)
    if (/\.pdf$/i.test(parsed.pathname)) return true
    // Chrome's built-in PDF viewer extension (stable ID).
    if (
      parsed.protocol === 'chrome-extension:' &&
      parsed.hostname === 'mhjfbmdgcfjbbpaeojofohoefgiehjai'
    ) {
      return true
    }
    if (parsed.protocol === 'chrome:' && /pdf/i.test(parsed.href)) return true
  } catch {
    return /\.pdf(\?|#|$)/i.test(url)
  }
  return false
}
