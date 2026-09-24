import {
  clampPixelCrop,
  cssRectToPixels,
  MIN_CROP_CSS_PX,
  type CssRect,
} from '../../../lib/vision-ocr-core.js'

async function blobToDataUrl(blob: Blob): Promise<string> {
  const buffer = await blob.arrayBuffer()
  const bytes = new Uint8Array(buffer)
  let binary = ''
  const chunk = 0x8000
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
  }
  return `data:image/png;base64,${btoa(binary)}`
}

/** ponytail: background SW has no `document`; OffscreenCanvas works in SW + extension pages. */
async function cropBitmapToPngDataUrl(
  bitmap: ImageBitmap,
  crop: { x: number; y: number; width: number; height: number }
): Promise<string> {
  if (typeof OffscreenCanvas !== 'undefined') {
    const canvas = new OffscreenCanvas(crop.width, crop.height)
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法裁切截图')
    ctx.drawImage(bitmap, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height)
    return blobToDataUrl(await canvas.convertToBlob({ type: 'image/png' }))
  }
  if (typeof document !== 'undefined') {
    const canvas = document.createElement('canvas')
    canvas.width = crop.width
    canvas.height = crop.height
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('无法裁切截图')
    ctx.drawImage(bitmap, crop.x, crop.y, crop.width, crop.height, 0, 0, crop.width, crop.height)
    return canvas.toDataURL('image/png')
  }
  throw new Error('当前环境无法裁切截图')
}

export async function cropDataUrlPng(
  dataUrl: string,
  cssRect: CssRect,
  dpr: number
): Promise<string> {
  const blob = await (await fetch(dataUrl)).blob()
  const bitmap = await createImageBitmap(blob)
  try {
    const crop = clampPixelCrop(cssRectToPixels(cssRect, dpr), bitmap.width, bitmap.height)
    if (crop.width < MIN_CROP_CSS_PX || crop.height < MIN_CROP_CSS_PX) {
      throw new Error('选区太小，请再拖一次')
    }
    return await cropBitmapToPngDataUrl(bitmap, crop)
  } finally {
    bitmap.close()
  }
}
