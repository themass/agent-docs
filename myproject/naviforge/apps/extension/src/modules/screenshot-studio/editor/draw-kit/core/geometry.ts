export type DrawPoint = { x: number; y: number }
export type DrawBounds = { x: number; y: number; width: number; height: number }
export type ResizeHandle = 'nw' | 'ne' | 'sw' | 'se'

export function normalizeBox(x1: number, y1: number, x2: number, y2: number): DrawBounds {
  const x = Math.min(x1, x2)
  const y = Math.min(y1, y2)
  return { x, y, width: Math.abs(x2 - x1), height: Math.abs(y2 - y1) }
}

export function distToSegment(px: number, py: number, x1: number, y1: number, x2: number, y2: number): number {
  const len = Math.hypot(x2 - x1, y2 - y1)
  if (len < 1) return Math.hypot(px - x1, py - y1)
  return Math.abs((y2 - y1) * px - (x2 - x1) * py + x2 * y1 - y2 * x1) / len
}

export function pointInBox(x: number, y: number, box: DrawBounds): boolean {
  return x >= box.x && x <= box.x + box.width && y >= box.y && y <= box.y + box.height
}

/** Canvas-accurate text box for hit tests and selection chrome. */
export function measureTextBounds(
  text: string,
  fontSize: number,
  fontWeight = 600
): DrawBounds {
  const canvas = document.createElement('canvas')
  const ctx = canvas.getContext('2d')
  if (!ctx) {
    const lines = text.split('\n').length
    return {
      x: 0,
      y: 0,
      width: Math.max(fontSize, text.length * fontSize * 0.55),
      height: fontSize * 1.25 * lines,
    }
  }
  ctx.font = `${fontWeight} ${fontSize}px system-ui, sans-serif`
  const lineTexts = text.split('\n')
  let width = fontSize
  for (const line of lineTexts) {
    width = Math.max(width, ctx.measureText(line).width)
  }
  return {
    x: 0,
    y: 0,
    width: Math.max(fontSize, width),
    height: fontSize * 1.25 * lineTexts.length,
  }
}

export function lineStrokeBounds(
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  stroke: number,
  headPad = 0
): DrawBounds {
  const pad = Math.max(8, stroke + 4) + headPad
  const box = normalizeBox(x1, y1, x2, y2)
  return {
    x: box.x - pad,
    y: box.y - pad,
    width: box.width + pad * 2,
    height: box.height + pad * 2,
  }
}

export function rotatedBounds(bounds: DrawBounds, rotationDeg = 0): DrawBounds {
  if (!rotationDeg) return bounds
  const cx = bounds.x + bounds.width / 2
  const cy = bounds.y + bounds.height / 2
  const corners = [
    { x: bounds.x, y: bounds.y },
    { x: bounds.x + bounds.width, y: bounds.y },
    { x: bounds.x, y: bounds.y + bounds.height },
    { x: bounds.x + bounds.width, y: bounds.y + bounds.height },
  ]
  const rad = (rotationDeg * Math.PI) / 180
  const cos = Math.cos(rad)
  const sin = Math.sin(rad)
  const rotated = corners.map((p) => {
    const dx = p.x - cx
    const dy = p.y - cy
    return { x: cx + dx * cos - dy * sin, y: cy + dx * sin + dy * cos }
  })
  const xs = rotated.map((p) => p.x)
  const ys = rotated.map((p) => p.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  return {
    x: minX,
    y: minY,
    width: Math.max(1, Math.max(...xs) - minX),
    height: Math.max(1, Math.max(...ys) - minY),
  }
}

export function withAnnotationRotation(
  ctx: CanvasRenderingContext2D,
  bounds: DrawBounds,
  rotationDeg: number | undefined,
  draw: () => void
): void {
  const rot = rotationDeg ?? 0
  if (!rot) {
    draw()
    return
  }
  const cx = bounds.x + bounds.width / 2
  const cy = bounds.y + bounds.height / 2
  ctx.save()
  ctx.translate(cx, cy)
  ctx.rotate((rot * Math.PI) / 180)
  ctx.translate(-cx, -cy)
  draw()
  ctx.restore()
}

export function annotationRotation(ann: { rotation?: number }): number {
  return ann.rotation ?? 0
}

export function resizeBox(
  handle: ResizeHandle,
  pointerX: number,
  pointerY: number,
  origin: DrawBounds
): DrawBounds {
  const right = origin.x + origin.width
  const bottom = origin.y + origin.height
  let x1 = origin.x
  let y1 = origin.y
  let x2 = right
  let y2 = bottom
  if (handle === 'nw') {
    x1 = pointerX
    y1 = pointerY
  } else if (handle === 'ne') {
    x2 = pointerX
    y1 = pointerY
  } else if (handle === 'sw') {
    x1 = pointerX
    y2 = pointerY
  } else {
    x2 = pointerX
    y2 = pointerY
  }
  const box = normalizeBox(x1, y1, x2, y2)
  return {
    x: box.x,
    y: box.y,
    width: Math.max(4, box.width),
    height: Math.max(4, box.height),
  }
}

const HANDLE_RADIUS = 6

export function hitResizeHandle(box: DrawBounds, x: number, y: number): ResizeHandle | null {
  const corners: Array<{ handle: ResizeHandle; cx: number; cy: number }> = [
    { handle: 'nw', cx: box.x, cy: box.y },
    { handle: 'ne', cx: box.x + box.width, cy: box.y },
    { handle: 'sw', cx: box.x, cy: box.y + box.height },
    { handle: 'se', cx: box.x + box.width, cy: box.y + box.height },
  ]
  for (const corner of corners) {
    if (Math.hypot(x - corner.cx, y - corner.cy) <= HANDLE_RADIUS + 4) return corner.handle
  }
  return null
}

export function drawResizeHandles(ctx: CanvasRenderingContext2D, box: DrawBounds): void {
  const corners = [
    { x: box.x, y: box.y },
    { x: box.x + box.width, y: box.y },
    { x: box.x, y: box.y + box.height },
    { x: box.x + box.width, y: box.y + box.height },
  ]
  ctx.fillStyle = '#70a91d'
  ctx.strokeStyle = '#0f1412'
  ctx.lineWidth = 1
  for (const corner of corners) {
    ctx.beginPath()
    ctx.arc(corner.x, corner.y, HANDLE_RADIUS, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
  }
}
