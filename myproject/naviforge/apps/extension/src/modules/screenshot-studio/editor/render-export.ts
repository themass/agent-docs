import type { StudioAnnotation } from '../types.js'
import {
  drawAnnotations,
  isRegionShape,
} from './draw-kit/core/shape-registry.js'
import { ensureDrawKit } from './draw-kit/index.js'

ensureDrawKit()

export async function renderStudioPng(
  baseImageDataUrl: string,
  annotations: StudioAnnotation[]
): Promise<string> {
  const bitmap = await createImageBitmap(await (await fetch(baseImageDataUrl)).blob())
  try {
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) throw new Error('无法导出截图')
    ctx.drawImage(bitmap, 0, 0)
    const env = { image: bitmap }
    const vector = annotations.filter((a) => !isRegionShape(a.type))
    const region = annotations.filter((a) => isRegionShape(a.type))
    drawAnnotations(ctx, vector, env)
    drawAnnotations(ctx, region, env)
    return canvas.toDataURL('image/png')
  } finally {
    bitmap.close()
  }
}

export async function copyPngToClipboard(dataUrl: string): Promise<void> {
  const blob = await (await fetch(dataUrl)).blob()
  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
}

export function downloadPng(dataUrl: string, filename: string): void {
  const anchor = document.createElement('a')
  anchor.href = dataUrl
  anchor.download = filename
  anchor.click()
}
