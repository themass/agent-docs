export type PageMetrics = {
  scrollY: number
  innerHeight: number
  innerWidth: number
  scrollHeight: number
  devicePixelRatio: number
}

export type CaptureSlice = {
  dataUrl: string
  scrollY: number
}

const DEFAULT_OVERLAP = 80
const MAX_SLICES = 50
const MAX_HEIGHT_PX = 20_000

/** Stitch viewport captures into one full-page PNG data URL. */
export async function stitchFullPage(
  slices: CaptureSlice[],
  metrics: PageMetrics,
  overlap = DEFAULT_OVERLAP
): Promise<{ dataUrl: string; width: number; height: number }> {
  if (!slices.length) throw new Error('no screenshot slices')
  const dpr = metrics.devicePixelRatio || 1
  const width = Math.ceil(metrics.innerWidth * dpr)
  const height = Math.min(Math.ceil(metrics.scrollHeight * dpr), MAX_HEIGHT_PX)
  const canvas = new OffscreenCanvas(width, height)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('OffscreenCanvas unavailable')

  for (const [index, slice] of slices.entries()) {
    const blob = await (await fetch(slice.dataUrl)).blob()
    const bitmap = await createImageBitmap(blob)
    const destY = Math.round(slice.scrollY * dpr)
    const cropTop = index > 0 ? Math.round(overlap * dpr) : 0
    const sourceHeight = Math.max(1, bitmap.height - cropTop)
    const drawHeight = Math.min(sourceHeight, height - destY)
    if (drawHeight <= 0) {
      bitmap.close()
      continue
    }
    ctx.drawImage(bitmap, 0, cropTop, bitmap.width, drawHeight, 0, destY, width, drawHeight)
    bitmap.close()
  }

  const out = await canvas.convertToBlob({ type: 'image/png' })
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsDataURL(out)
  })
  return { dataUrl, width, height }
}

export function slicePlan(metrics: PageMetrics, overlap = DEFAULT_OVERLAP): number[] {
  const step = Math.max(120, metrics.innerHeight - overlap)
  const positions: number[] = []
  for (let y = 0; y < metrics.scrollHeight && positions.length < MAX_SLICES; y += step) {
    positions.push(y)
  }
  const last = metrics.scrollHeight - metrics.innerHeight
  if (last > 0 && (positions.at(-1) ?? 0) < last) positions.push(last)
  return positions
}

export function friendlyCaptureError(raw: string): string {
  if (/MAX_CAPTURE_VISIBLE_TAB|quota/i.test(raw)) {
    return '截图太快被浏览器拦住了，请等一秒再试'
  }
  if (/activeTab/i.test(raw)) {
    return '截图需要目标网页在前台。请先打开普通网页再截。'
  }
  if (/not visible|not in the foreground|cannot be captured/i.test(raw)) {
    return '当前标签不在前台，请点回网页再截。'
  }
  if (/No tab with id|The tab was closed/i.test(raw)) {
    return '要截的标签已经关掉了，请打开网页再试。'
  }
  if (/Cannot access contents of url|Cannot access a chrome/i.test(raw)) {
    return '浏览器内部页无法截图，请换到普通网页。'
  }
  return raw
}
