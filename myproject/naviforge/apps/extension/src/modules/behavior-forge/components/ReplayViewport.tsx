import { useEffect, useMemo, useRef } from 'react'

import type { BehaviorEvent, BehaviorSessionRecord } from '../types.js'
import { normalizeSessionEvents, replayDurationMs } from '../replay-utils.js'
import { positionAtTime, smoothPath, type Point } from '../smooth-path.js'
import { ReplayScreenShell } from './ReplayScreenShell.js'

type Props = {
  session: BehaviorSessionRecord
  timeMs: number
  onDuration: (ms: number) => void
}

function collectPointerData(events: BehaviorEvent[]): {
  times: number[]
  points: Point[]
  clicks: Array<{ t: number; x: number; y: number }>
  viewport: { w: number; h: number }
} {
  const times: number[] = []
  const points: Point[] = []
  const clicks: Array<{ t: number; x: number; y: number }> = []
  let viewport = { w: 1280, h: 720 }
  for (const e of events) {
    if (e.kind === 'viewport') viewport = { w: e.w, h: e.h }
    if (e.kind === 'pointer') {
      times.push(e.t)
      points.push({ x: e.x, y: e.y })
    }
    if (e.kind === 'click') clicks.push({ t: e.t, x: e.x, y: e.y })
  }
  return { times, points, clicks, viewport }
}

export function ReplayViewport({ session, timeMs, onDuration }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const stageRef = useRef<HTMLDivElement>(null)

  const events = useMemo(() => normalizeSessionEvents(session.events), [session.events])
  const { times, points, clicks, viewport } = useMemo(
    () => collectPointerData(events),
    [events]
  )
  const path = useMemo(() => smoothPath(points, 6), [points])
  const durationMs = useMemo(() => replayDurationMs(session), [session])

  useEffect(() => {
    onDuration(durationMs)
  }, [durationMs, onDuration])

  useEffect(() => {
    const canvas = canvasRef.current
    const stage = stageRef.current
    if (!canvas || !stage) return

    const draw = () => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return

      const rect = stage.getBoundingClientRect()
      const w = Math.max(1, rect.width)
      const h = Math.max(1, rect.height)
      canvas.width = w * devicePixelRatio
      canvas.height = h * devicePixelRatio
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)

      const pad = 16
      const availW = w - pad * 2
      const availH = h - pad * 2
      const scale = Math.min(availW / viewport.w, availH / viewport.h)
      const screenW = viewport.w * scale
      const screenH = viewport.h * scale
      const offsetX = (w - screenW) / 2
      const offsetY = (h - screenH) / 2

      ctx.fillStyle = '#2a2824'
      ctx.fillRect(0, 0, w, h)

      ctx.fillStyle = '#ffffff'
      ctx.shadowColor = 'rgba(0,0,0,0.35)'
      ctx.shadowBlur = 24
      ctx.shadowOffsetY = 8
      ctx.fillRect(offsetX, offsetY, screenW, screenH)
      ctx.shadowColor = 'transparent'

      const map = (p: Point): Point => ({
        x: offsetX + p.x * scale,
        y: offsetY + p.y * scale,
      })

      ctx.save()
      ctx.beginPath()
      ctx.rect(offsetX, offsetY, screenW, screenH)
      ctx.clip()

      ctx.strokeStyle = 'rgba(23,33,31,0.05)'
      ctx.lineWidth = 1
      for (let x = offsetX; x <= offsetX + screenW; x += 32 * scale) {
        ctx.beginPath()
        ctx.moveTo(x, offsetY)
        ctx.lineTo(x, offsetY + screenH)
        ctx.stroke()
      }
      for (let y = offsetY; y <= offsetY + screenH; y += 32 * scale) {
        ctx.beginPath()
        ctx.moveTo(offsetX, y)
        ctx.lineTo(offsetX + screenW, y)
        ctx.stroke()
      }

      if (path.length > 1) {
        const mapped = path.map(map)
        const grad = ctx.createLinearGradient(
          mapped[0]!.x,
          mapped[0]!.y,
          mapped.at(-1)!.x,
          mapped.at(-1)!.y
        )
        grad.addColorStop(0, 'rgba(112,169,29,0.2)')
        grad.addColorStop(1, 'rgba(112,169,29,0.9)')
        ctx.strokeStyle = grad
        ctx.lineWidth = Math.max(2, 2.5 * scale)
        ctx.lineJoin = 'round'
        ctx.lineCap = 'round'
        ctx.beginPath()
        ctx.moveTo(mapped[0]!.x, mapped[0]!.y)
        for (let i = 1; i < mapped.length; i++) ctx.lineTo(mapped[i]!.x, mapped[i]!.y)
        ctx.stroke()
      }

      for (const click of clicks) {
        if (click.t > timeMs) continue
        const p = map({ x: click.x, y: click.y })
        const age = (timeMs - click.t) / 1000
        const radius = (6 + Math.min(18, age * 12)) * scale
        const alpha = Math.max(0, 0.5 - age * 0.35)
        ctx.strokeStyle = `rgba(255, 92, 53, ${alpha})`
        ctx.lineWidth = Math.max(1.5, 2 * scale)
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
        ctx.stroke()
      }

      const cursor = positionAtTime(times, path, timeMs)
      if (cursor) {
        const p = map(cursor)
        const r = Math.max(5, 7 * scale)
        ctx.fillStyle = '#70a91d'
        ctx.strokeStyle = '#171d1b'
        ctx.lineWidth = Math.max(1.5, 2 * scale)
        ctx.beginPath()
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
      }

      ctx.restore()
    }

    draw()
    const ro = new ResizeObserver(draw)
    ro.observe(stage)
    return () => ro.disconnect()
  }, [path, times, clicks, viewport, timeMs])

  return (
    <div className="bf-replay-wrap">
      <ReplayScreenShell url={session.originUrl} viewport={viewport}>
        <div ref={stageRef} className="bf-screen-stage-inner">
          <canvas ref={canvasRef} className="bf-trail-canvas" aria-label="Mouse trail viewport" />
        </div>
      </ReplayScreenShell>
    </div>
  )
}
