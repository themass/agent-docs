import {
  distToSegment,
  lineStrokeBounds,
  measureTextBounds,
  normalizeBox,
  pointInBox,
  resizeBox,
  withAnnotationRotation,
  type DrawBounds,
} from '../core/geometry.js'
import type { DrawEnv } from '../core/shape-definition.js'
import { registerShapeDefinition } from '../core/shape-registry.js'

export function drawStrokeLine(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  stroke: number
): void {
  ctx.strokeStyle = color
  ctx.lineWidth = stroke
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(x2, y2)
  ctx.stroke()
}

export function drawArrowHead(
  ctx: CanvasRenderingContext2D,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  color: string,
  stroke: number
): void {
  const dx = x2 - x1
  const dy = y2 - y1
  const len = Math.hypot(dx, dy)
  if (len < 2) return

  const angle = Math.atan2(dy, dx)
  const headLen = Math.max(stroke * 3.2, 14)
  const headHalf = Math.max(stroke * 1.35, 7)
  const tipX = x2
  const tipY = y2
  const baseX = tipX - headLen * Math.cos(angle)
  const baseY = tipY - headLen * Math.sin(angle)
  const perpX = Math.sin(angle)
  const perpY = -Math.cos(angle)

  ctx.strokeStyle = color
  ctx.fillStyle = color
  ctx.lineWidth = stroke
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'

  ctx.beginPath()
  ctx.moveTo(x1, y1)
  ctx.lineTo(baseX, baseY)
  ctx.stroke()

  ctx.beginPath()
  ctx.moveTo(tipX, tipY)
  ctx.lineTo(baseX + perpX * headHalf, baseY + perpY * headHalf)
  ctx.lineTo(baseX - perpX * headHalf, baseY - perpY * headHalf)
  ctx.closePath()
  ctx.fill()
}

export function drawPathStroke(
  ctx: CanvasRenderingContext2D,
  points: Array<{ x: number; y: number }>,
  color: string,
  stroke: number,
  alpha = 1
): void {
  if (points.length < 2) return
  ctx.save()
  ctx.globalAlpha = alpha
  ctx.strokeStyle = color
  ctx.lineWidth = stroke
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  ctx.beginPath()
  ctx.moveTo(points[0]!.x, points[0]!.y)
  for (let i = 1; i < points.length; i++) ctx.lineTo(points[i]!.x, points[i]!.y)
  ctx.stroke()
  ctx.restore()
}

function lineBounds(x1: number, y1: number, x2: number, y2: number): DrawBounds {
  return normalizeBox(x1, y1, x2, y2)
}

function arrowHeadPad(stroke: number): number {
  return Math.max(stroke * 3.2, 14)
}

function translateLine<T extends { x1: number; y1: number; x2: number; y2: number }>(
  ann: T,
  dx: number,
  dy: number
): T {
  return { ...ann, x1: ann.x1 + dx, y1: ann.y1 + dy, x2: ann.x2 + dx, y2: ann.y2 + dy }
}

function translatePath<T extends { points: Array<{ x: number; y: number }> }>(
  ann: T,
  dx: number,
  dy: number
): T {
  return {
    ...ann,
    points: ann.points.map((p) => ({ x: p.x + dx, y: p.y + dy })),
  }
}

function translateBox<T extends { x: number; y: number }>(ann: T, dx: number, dy: number): T {
  return { ...ann, x: ann.x + dx, y: ann.y + dy }
}

function drawMosaicRegion(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  block: number
): void {
  const safeBlock = Math.max(4, block)
  for (let py = y; py < y + height; py += safeBlock) {
    for (let px = x; px < x + width; px += safeBlock) {
      const w = Math.min(safeBlock, x + width - px)
      const h = Math.min(safeBlock, y + height - py)
      const sample = ctx.getImageData(px + w / 2, py + h / 2, 1, 1).data
      ctx.fillStyle = `rgb(${sample[0]},${sample[1]},${sample[2]})`
      ctx.fillRect(px, py, w, h)
    }
  }
}

function drawBlurRegion(
  ctx: CanvasRenderingContext2D,
  image: CanvasImageSource,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
): void {
  ctx.save()
  ctx.beginPath()
  ctx.rect(x, y, width, height)
  ctx.clip()
  ctx.filter = `blur(${Math.max(2, radius)}px)`
  ctx.drawImage(image, 0, 0)
  ctx.restore()
  ctx.filter = 'none'
}

export function registerAllShapes(): void {
  registerShapeDefinition({
    type: 'rect',
    layer: 'vector',
    traits: { stroke: true, rotatable: true },
    bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.width, height: ann.height }),
    draw: (ctx, ann) => {
      const bounds = { x: ann.x, y: ann.y, width: ann.width, height: ann.height }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        ctx.strokeStyle = ann.color
        ctx.lineWidth = ann.stroke
        ctx.strokeRect(ann.x, ann.y, ann.width, ann.height)
      })
    },
    hitTest: (ann, x, y) => pointInBox(x, y, ann),
    translate: translateBox,
    resize: (ann, handle, x, y, origin) => ({ ...ann, ...resizeBox(handle, x, y, origin) }),
  })

  registerShapeDefinition({
    type: 'ellipse',
    layer: 'vector',
    traits: { stroke: true, rotatable: true },
    bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.width, height: ann.height }),
    draw: (ctx, ann) => {
      const bounds = { x: ann.x, y: ann.y, width: ann.width, height: ann.height }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        const cx = ann.x + ann.width / 2
        const cy = ann.y + ann.height / 2
        const rx = ann.width / 2
        const ry = ann.height / 2
        ctx.strokeStyle = ann.color
        ctx.lineWidth = ann.stroke
        ctx.beginPath()
        ctx.ellipse(cx, cy, Math.max(1, rx), Math.max(1, ry), 0, 0, Math.PI * 2)
        ctx.stroke()
      })
    },
    hitTest: (ann, x, y) => {
      const cx = ann.x + ann.width / 2
      const cy = ann.y + ann.height / 2
      const rx = Math.max(1, ann.width / 2)
      const ry = Math.max(1, ann.height / 2)
      const nx = (x - cx) / rx
      const ny = (y - cy) / ry
      return nx * nx + ny * ny <= 1.08
    },
    translate: translateBox,
    resize: (ann, handle, x, y, origin) => ({ ...ann, ...resizeBox(handle, x, y, origin) }),
  })

  registerShapeDefinition({
    type: 'arrow',
    layer: 'vector',
    traits: { stroke: true, rotatable: true },
    bounds: (ann) =>
      lineStrokeBounds(ann.x1, ann.y1, ann.x2, ann.y2, ann.stroke, arrowHeadPad(ann.stroke)),
    draw: (ctx, ann) => {
      const bounds = lineStrokeBounds(
        ann.x1,
        ann.y1,
        ann.x2,
        ann.y2,
        ann.stroke,
        arrowHeadPad(ann.stroke)
      )
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        drawArrowHead(ctx, ann.x1, ann.y1, ann.x2, ann.y2, ann.color, ann.stroke)
      })
    },
    hitTest: (ann, x, y) =>
      distToSegment(x, y, ann.x1, ann.y1, ann.x2, ann.y2) < Math.max(8, ann.stroke + 4),
    translate: translateLine,
  })

  registerShapeDefinition({
    type: 'line',
    layer: 'vector',
    traits: { stroke: true, rotatable: true },
    bounds: (ann) => lineStrokeBounds(ann.x1, ann.y1, ann.x2, ann.y2, ann.stroke),
    draw: (ctx, ann) => {
      const bounds = lineStrokeBounds(ann.x1, ann.y1, ann.x2, ann.y2, ann.stroke)
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        drawStrokeLine(ctx, ann.x1, ann.y1, ann.x2, ann.y2, ann.color, ann.stroke)
      })
    },
    hitTest: (ann, x, y) =>
      distToSegment(x, y, ann.x1, ann.y1, ann.x2, ann.y2) < Math.max(8, ann.stroke + 4),
    translate: translateLine,
  })

  registerShapeDefinition({
    type: 'pen',
    layer: 'vector',
    traits: { stroke: true, rotatable: true },
    bounds: (ann) => {
      const xs = ann.points.map((p) => p.x)
      const ys = ann.points.map((p) => p.y)
      const minX = Math.min(...xs)
      const minY = Math.min(...ys)
      const pad = Math.max(8, ann.stroke + 4)
      return {
        x: minX - pad,
        y: minY - pad,
        width: Math.max(...xs) - minX + pad * 2,
        height: Math.max(...ys) - minY + pad * 2,
      }
    },
    draw: (ctx, ann) => {
      const xs = ann.points.map((p) => p.x)
      const ys = ann.points.map((p) => p.y)
      const pad = Math.max(8, ann.stroke + 4)
      const bounds = {
        x: Math.min(...xs) - pad,
        y: Math.min(...ys) - pad,
        width: Math.max(...xs) - Math.min(...xs) + pad * 2,
        height: Math.max(...ys) - Math.min(...ys) + pad * 2,
      }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        drawPathStroke(ctx, ann.points, ann.color, ann.stroke, 1)
      })
    },
    hitTest: (ann, x, y) => {
      for (let i = 1; i < ann.points.length; i++) {
        const a = ann.points[i - 1]!
        const b = ann.points[i]!
        if (distToSegment(x, y, a.x, a.y, b.x, b.y) < Math.max(8, ann.stroke + 4)) return true
      }
      return false
    },
    translate: translatePath,
  })

  registerShapeDefinition({
    type: 'highlighter',
    layer: 'vector',
    traits: { highlighterStroke: true, rotatable: true },
    bounds: (ann) => {
      const xs = ann.points.map((p) => p.x)
      const ys = ann.points.map((p) => p.y)
      const minX = Math.min(...xs)
      const minY = Math.min(...ys)
      const pad = Math.max(12, ann.stroke + 6)
      return {
        x: minX - pad,
        y: minY - pad,
        width: Math.max(...xs) - minX + pad * 2,
        height: Math.max(...ys) - minY + pad * 2,
      }
    },
    draw: (ctx, ann) => {
      const xs = ann.points.map((p) => p.x)
      const ys = ann.points.map((p) => p.y)
      const pad = Math.max(12, ann.stroke + 6)
      const bounds = {
        x: Math.min(...xs) - pad,
        y: Math.min(...ys) - pad,
        width: Math.max(...xs) - Math.min(...xs) + pad * 2,
        height: Math.max(...ys) - Math.min(...ys) + pad * 2,
      }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        drawPathStroke(ctx, ann.points, ann.color, ann.stroke, 0.38)
      })
    },
    hitTest: (ann, x, y) => {
      for (let i = 1; i < ann.points.length; i++) {
        const a = ann.points[i - 1]!
        const b = ann.points[i]!
        if (distToSegment(x, y, a.x, a.y, b.x, b.y) < Math.max(12, ann.stroke + 6)) return true
      }
      return false
    },
    translate: translatePath,
  })

  registerShapeDefinition({
    type: 'text',
    layer: 'vector',
    traits: { fontSize: true, rotatable: true },
    bounds: (ann) => {
      const local = measureTextBounds(ann.text, ann.fontSize)
      return { x: ann.x, y: ann.y, width: local.width, height: local.height }
    },
    draw: (ctx, ann) => {
      const local = measureTextBounds(ann.text, ann.fontSize)
      const bounds = { x: ann.x, y: ann.y, width: local.width, height: local.height }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        ctx.fillStyle = ann.color
        ctx.font = `600 ${ann.fontSize}px system-ui, sans-serif`
        ctx.textBaseline = 'top'
        for (const [index, line] of ann.text.split('\n').entries()) {
          ctx.fillText(line, ann.x, ann.y + index * (ann.fontSize * 1.25))
        }
      })
    },
    hitTest: (ann, x, y) => pointInBox(x, y, registryBoundsText(ann)),
    translate: (ann, dx, dy) => ({ ...ann, x: ann.x + dx, y: ann.y + dy }),
  })

  registerShapeDefinition({
    type: 'marker',
    layer: 'vector',
    traits: { markerSize: true, rotatable: true },
    bounds: (ann) => {
      const r = ann.size / 2
      return { x: ann.x - r, y: ann.y - r, width: ann.size, height: ann.size }
    },
    draw: (ctx, ann) => {
      const r = ann.size / 2
      const bounds = { x: ann.x - r, y: ann.y - r, width: ann.size, height: ann.size }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        ctx.fillStyle = ann.color
        ctx.strokeStyle = '#0f1412'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(ann.x, ann.y, r, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        ctx.fillStyle = ann.color === '#ffffff' || ann.color === '#f59e0b' ? '#0f1412' : '#fff'
        ctx.font = `700 ${Math.round(ann.size * 0.55)}px system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText(String(ann.n), ann.x, ann.y + 1)
        ctx.textAlign = 'start'
        ctx.textBaseline = 'alphabetic'
      })
    },
    hitTest: (ann, x, y) => {
      const r = ann.size / 2 + 4
      return Math.hypot(x - ann.x, y - ann.y) <= r
    },
    translate: (ann, dx, dy) => ({ ...ann, x: ann.x + dx, y: ann.y + dy }),
    resize: (ann, handle, x, y, origin) => {
      const r = origin.size / 2
      const originBox = { x: origin.x - r, y: origin.y - r, width: origin.size, height: origin.size }
      const box = resizeBox(handle, x, y, originBox)
      const size = Math.max(16, Math.round(Math.max(box.width, box.height)))
      return { ...ann, x: box.x + size / 2, y: box.y + size / 2, size }
    },
  })

  registerShapeDefinition({
    type: 'sticker',
    layer: 'vector',
    traits: { stickerSize: true, rotatable: true },
    bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.size, height: ann.size }),
    draw: (ctx, ann) => {
      const bounds = { x: ann.x, y: ann.y, width: ann.size, height: ann.size }
      withAnnotationRotation(ctx, bounds, ann.rotation, () => {
        ctx.font = `${ann.size}px system-ui, emoji`
        ctx.textBaseline = 'top'
        ctx.fillText(ann.emoji, ann.x, ann.y)
      })
    },
    hitTest: (ann, x, y) => pointInBox(x, y, { x: ann.x, y: ann.y, width: ann.size, height: ann.size }),
    translate: translateBox,
    resize: (ann, handle, x, y, origin) => {
      const originBox = { x: origin.x, y: origin.y, width: origin.size, height: origin.size }
      const box = resizeBox(handle, x, y, originBox)
      const size = Math.max(16, Math.round(Math.max(box.width, box.height)))
      return { ...ann, x: box.x, y: box.y, size }
    },
  })

  registerShapeDefinition({
    type: 'mosaic',
    layer: 'region',
    traits: { mosaicBlock: true },
    bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.width, height: ann.height }),
    draw: (ctx, ann, env) => {
      if (!env.image) return
      drawMosaicRegion(ctx, ann.x, ann.y, ann.width, ann.height, ann.block)
    },
    hitTest: (ann, x, y) => pointInBox(x, y, ann),
    translate: translateBox,
    resize: (ann, handle, x, y, origin) => ({ ...ann, ...resizeBox(handle, x, y, origin) }),
  })

  registerShapeDefinition({
    type: 'blur',
    layer: 'region',
    traits: { blurRadius: true },
    bounds: (ann) => ({ x: ann.x, y: ann.y, width: ann.width, height: ann.height }),
    draw: (ctx, ann, env) => {
      if (!env.image) return
      drawBlurRegion(ctx, env.image, ann.x, ann.y, ann.width, ann.height, ann.radius)
    },
    hitTest: (ann, x, y) => pointInBox(x, y, ann),
    translate: translateBox,
    resize: (ann, handle, x, y, origin) => ({ ...ann, ...resizeBox(handle, x, y, origin) }),
  })
}

function registryBoundsText(ann: { x: number; y: number; text: string; fontSize: number }) {
  const local = measureTextBounds(ann.text, ann.fontSize)
  return { x: ann.x, y: ann.y, width: local.width, height: local.height }
}
