import { normalizeBox, hitResizeHandle } from '../core/geometry.js'
import {
  annotationBounds,
  hitTestAnnotation,
  resizeAnnotation,
  translateAnnotation,
} from '../core/shape-registry.js'
import { drawArrowHead, drawPathStroke, drawStrokeLine } from '../shapes/register-shapes.js'
import type { PointerEvent } from 'react'
import type { StudioAnnotation, StudioTool } from '../annotation-types.js'

import type { DrawPoint } from '../core/geometry.js'

export type EditorBridge = {
  tool: StudioTool
  color: string
  stroke: number
  highlighterStroke: number
  fontSize: number
  mosaicBlock: number
  blurRadius: number
  stickerEmoji: string
  stickerSize: number
  textDraft: string
  markerNext: number
  annotations: StudioAnnotation[]
  beginGesture: () => void
  setAnnotationsLive: (next: StudioAnnotation[]) => void
  addAnnotation: (item: Omit<StudioAnnotation, 'id'> | StudioAnnotation) => string
  setMarkerNext: (n: number) => void
}

export type DragState =
  | {
      kind: 'create-box'
      shape: 'rect' | 'ellipse' | 'mosaic' | 'blur'
      startX: number
      startY: number
      currentX: number
      currentY: number
    }
  | {
      kind: 'create-line'
      shape: 'arrow' | 'line'
      startX: number
      startY: number
      currentX: number
      currentY: number
    }
  | { kind: 'create-path'; shape: 'pen' | 'highlighter'; points: DrawPoint[] }
  | {
      kind: 'move'
      id: string
      startX: number
      startY: number
      snapshot: StudioAnnotation
    }
  | {
      kind: 'resize'
      id: string
      handle: 'nw' | 'ne' | 'sw' | 'se'
      startX: number
      startY: number
      snapshot: StudioAnnotation
    }
  | {
      kind: 'rotate'
      id: string
      centerX: number
      centerY: number
      startPointerAngle: number
      startRotation: number
      snapshot: StudioAnnotation
    }

export type PointerSession = {
  editor: EditorBridge
  drag: DragState | null
  setDrag: (drag: DragState | null) => void
  selectedId: string | null
  setSelectedId: (id: string | null) => void
  toImageCoords: (clientX: number, clientY: number) => DrawPoint
  /** Switch to select tool when clicking an existing annotation. */
  activateSelect?: () => void
}

function replaceLive(session: PointerSession, id: string, next: StudioAnnotation) {
  session.editor.setAnnotationsLive(
    session.editor.annotations.map((item) => (item.id === id ? next : item))
  )
}

function startMove(
  session: PointerSession,
  event: React.PointerEvent<HTMLCanvasElement>,
  hit: StudioAnnotation,
  point: DrawPoint
) {
  session.setSelectedId(hit.id)
  event.currentTarget.setPointerCapture(event.pointerId)
  session.editor.beginGesture()
  session.setDrag({
    kind: 'move',
    id: hit.id,
    startX: point.x,
    startY: point.y,
    snapshot: { ...hit },
  })
}

export function handlePointerDown(session: PointerSession, event: React.PointerEvent<HTMLCanvasElement>) {
  const point = session.toImageCoords(event.clientX, event.clientY)
  const editor = session.editor
  const hit = hitTestAnnotation(editor.annotations, point.x, point.y) as StudioAnnotation | undefined

  if (!hit && session.selectedId) {
    session.setSelectedId(null)
    return
  }

  const selected = session.selectedId
    ? editor.annotations.find((item) => item.id === session.selectedId)
    : undefined
  if (selected) {
    const handle = hitResizeHandle(annotationBounds(selected), point.x, point.y)
    if (handle) {
      event.currentTarget.setPointerCapture(event.pointerId)
      editor.beginGesture()
      session.setDrag({
        kind: 'resize',
        id: selected.id,
        handle,
        startX: point.x,
        startY: point.y,
        snapshot: { ...selected },
      })
      return
    }
  }

  if (editor.tool === 'text') {
    if (hit?.type === 'text') {
      startMove(session, event, hit, point)
      return
    }
    return
  }

  if (editor.tool === 'sticker') {
    if (hit?.type === 'sticker') {
      startMove(session, event, hit, point)
      return
    }
    return
  }

  if (editor.tool === 'marker') {
    if (hit) {
      startMove(session, event, hit, point)
      return
    }
    editor.addAnnotation({
      type: 'marker',
      x: point.x,
      y: point.y,
      n: editor.markerNext,
      color: editor.color,
      size: 28,
    })
    editor.setMarkerNext(editor.markerNext + 1)
    return
  }

  if (hit) {
    startMove(session, event, hit, point)
    return
  }

  if (editor.tool === 'select') {
    session.setSelectedId(null)
    return
  }

  event.currentTarget.setPointerCapture(event.pointerId)

  if (editor.tool === 'pen' || editor.tool === 'highlighter') {
    session.setDrag({
      kind: 'create-path',
      shape: editor.tool,
      points: [{ x: point.x, y: point.y }],
    })
    return
  }

  if (editor.tool === 'arrow' || editor.tool === 'line') {
    session.setDrag({
      kind: 'create-line',
      shape: editor.tool,
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    })
    return
  }

  if (
    editor.tool === 'rect' ||
    editor.tool === 'ellipse' ||
    editor.tool === 'mosaic' ||
    editor.tool === 'blur'
  ) {
    session.setDrag({
      kind: 'create-box',
      shape: editor.tool,
      startX: point.x,
      startY: point.y,
      currentX: point.x,
      currentY: point.y,
    })
  }
}

export function handlePointerMove(session: PointerSession, event: React.PointerEvent<HTMLCanvasElement>) {
  const drag = session.drag
  if (!drag) return
  const point = session.toImageCoords(event.clientX, event.clientY)

  if (drag.kind === 'move') {
    const dx = point.x - drag.startX
    const dy = point.y - drag.startY
    replaceLive(
      session,
      drag.id,
      translateAnnotation(drag.snapshot, dx, dy) as StudioAnnotation
    )
    return
  }

  if (drag.kind === 'rotate') {
    const angle = Math.atan2(point.y - drag.centerY, point.x - drag.centerX)
    const deltaDeg = ((angle - drag.startPointerAngle) * 180) / Math.PI
    replaceLive(session, drag.id, {
      ...drag.snapshot,
      rotation: drag.startRotation + deltaDeg,
    } as StudioAnnotation)
    return
  }

  if (drag.kind === 'resize') {
    const current = session.editor.annotations.find((item) => item.id === drag.id)
    if (!current) return
    replaceLive(
      session,
      drag.id,
      resizeAnnotation(current, drag.handle, point.x, point.y, drag.snapshot) as StudioAnnotation
    )
    return
  }

  if (drag.kind === 'create-path') {
    const last = drag.points[drag.points.length - 1]
    if (!last || Math.hypot(point.x - last.x, point.y - last.y) >= 2) {
      session.setDrag({ ...drag, points: [...drag.points, { x: point.x, y: point.y }] })
    }
    return
  }

  if (drag.kind === 'create-box' || drag.kind === 'create-line') {
    session.setDrag({ ...drag, currentX: point.x, currentY: point.y })
  }
}

function finishCreate(session: PointerSession, createdId: string | null) {
  session.setDrag(null)
  if (createdId) session.setSelectedId(createdId)
}

export function handlePointerUp(session: PointerSession) {
  const drag = session.drag
  if (!drag) return
  const editor = session.editor

  if (drag.kind === 'move' || drag.kind === 'resize' || drag.kind === 'rotate') {
    session.setDrag(null)
    return
  }

  if (drag.kind === 'create-path') {
    if (drag.points.length >= 2) {
      if (drag.shape === 'pen') {
        finishCreate(
          session,
          editor.addAnnotation({
            type: 'pen',
            points: drag.points,
            color: editor.color,
            stroke: editor.stroke,
          })
        )
        return
      }
      finishCreate(
        session,
        editor.addAnnotation({
          type: 'highlighter',
          points: drag.points,
          color: editor.color,
          stroke: editor.highlighterStroke,
        })
      )
      return
    }
    session.setDrag(null)
    return
  }

  const box = normalizeBox(drag.startX, drag.startY, drag.currentX, drag.currentY)
  const lineLen = Math.hypot(drag.currentX - drag.startX, drag.currentY - drag.startY)

  if (drag.kind === 'create-line') {
    if (lineLen >= 4) {
      if (drag.shape === 'arrow') {
        finishCreate(
          session,
          editor.addAnnotation({
            type: 'arrow',
            x1: drag.startX,
            y1: drag.startY,
            x2: drag.currentX,
            y2: drag.currentY,
            color: editor.color,
            stroke: editor.stroke,
          })
        )
        return
      }
      finishCreate(
        session,
        editor.addAnnotation({
          type: 'line',
          x1: drag.startX,
          y1: drag.startY,
          x2: drag.currentX,
          y2: drag.currentY,
          color: editor.color,
          stroke: editor.stroke,
        })
      )
      return
    }
    session.setDrag(null)
    return
  }

  if (drag.kind === 'create-box' && box.width >= 4 && box.height >= 4) {
    if (drag.shape === 'rect') {
      finishCreate(
        session,
        editor.addAnnotation({ type: 'rect', ...box, color: editor.color, stroke: editor.stroke })
      )
      return
    }
    if (drag.shape === 'ellipse') {
      finishCreate(
        session,
        editor.addAnnotation({ type: 'ellipse', ...box, color: editor.color, stroke: editor.stroke })
      )
      return
    }
    if (drag.shape === 'mosaic') {
      finishCreate(session, editor.addAnnotation({ type: 'mosaic', ...box, block: editor.mosaicBlock }))
      return
    }
    if (drag.shape === 'blur') {
      finishCreate(session, editor.addAnnotation({ type: 'blur', ...box, radius: editor.blurRadius }))
      return
    }
  }
  session.setDrag(null)
}

export function paintDragPreview(
  ctx: CanvasRenderingContext2D,
  drag: DragState,
  editor: EditorBridge
): void {
  if (drag.kind === 'create-box') {
    const box = normalizeBox(drag.startX, drag.startY, drag.currentX, drag.currentY)
    ctx.strokeStyle = editor.color
    ctx.lineWidth = editor.stroke
    ctx.setLineDash(drag.shape === 'mosaic' || drag.shape === 'blur' ? [6, 4] : [])
    if (drag.shape === 'ellipse') {
      const cx = box.x + box.width / 2
      const cy = box.y + box.height / 2
      ctx.beginPath()
      ctx.ellipse(cx, cy, Math.max(1, box.width / 2), Math.max(1, box.height / 2), 0, 0, Math.PI * 2)
      ctx.stroke()
    } else {
      ctx.strokeRect(box.x, box.y, box.width, box.height)
    }
    ctx.setLineDash([])
    return
  }
  if (drag.kind === 'create-line') {
    if (drag.shape === 'arrow') {
      drawArrowHead(ctx, drag.startX, drag.startY, drag.currentX, drag.currentY, editor.color, editor.stroke)
    } else {
      drawStrokeLine(
        ctx,
        drag.startX,
        drag.startY,
        drag.currentX,
        drag.currentY,
        editor.color,
        editor.stroke
      )
    }
    return
  }
  if (drag.kind === 'create-path') {
    const stroke = drag.shape === 'highlighter' ? editor.highlighterStroke : editor.stroke
    const alpha = drag.shape === 'highlighter' ? 0.38 : 1
    drawPathStroke(ctx, drag.points, editor.color, stroke, alpha)
  }
}
