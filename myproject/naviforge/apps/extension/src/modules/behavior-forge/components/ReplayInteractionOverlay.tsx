import { useEffect, useMemo, useRef } from 'react'

import type { BehaviorEvent, BehaviorSessionRecord } from '../types.js'
import type { ReplayLayout } from '../replay-fit.js'
import { normalizeSessionEvents } from '../replay-utils.js'
import { positionAtTime, smoothPath, type Point } from '../smooth-path.js'

type Props = {
  session: BehaviorSessionRecord
  timeMs: number
  viewport: { w: number; h: number }
  layout?: ReplayLayout | null
}

function collect(events: BehaviorEvent[]) {
  const times: number[] = []
  const points: Point[] = []
  const clicks: Array<{ t: number; x: number; y: number }> = []
  const scrolls: Array<{ t: number; x: number; y: number }> = []
  for (const e of events) {
    if (e.kind === 'pointer') {
      times.push(e.t)
      points.push({ x: e.x, y: e.y })
    }
    if (e.kind === 'click') clicks.push({ t: e.t, x: e.x, y: e.y })
    if (e.kind === 'scroll') scrolls.push({ t: e.t, x: e.scrollX, y: e.scrollY })
  }
  return { times, points, clicks, scrolls, path: smoothPath(points, 6) }
}

export function ReplayInteractionOverlay({ session, timeMs, viewport, layout }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const events = useMemo(() => normalizeSessionEvents(session.events), [session.events])
  const { times, path, clicks, scrolls } = useMemo(() => collect(events), [events])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const parent = canvas.parentElement
    if (!parent) return

    const draw = () => {
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      const rect = parent.getBoundingClientRect()
      const w = rect.width
      const h = rect.height
      canvas.width = w * devicePixelRatio
      canvas.height = h * devicePixelRatio
      canvas.style.width = `${w}px`
      canvas.style.height = `${h}px`
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)
      ctx.clearRect(0, 0, w, h)

      const viewW = layout?.viewW ?? viewport.w
      const viewH = layout?.viewH ?? viewport.h
      let map: (p: Point) => Point
      if (layout && layout.width > 0 && layout.height > 0) {
        map = (p) => ({
          x: layout.left + (p.x / viewW) * layout.width,
          y: layout.top + (p.y / viewH) * layout.height,
        })
      } else {
        const pad = 12
        const scale = Math.min((w - pad * 2) / viewW, (h - pad * 2) / viewH)
        const screenW = viewW * scale
        const screenH = viewH * scale
        const ox = (w - screenW) / 2
        const oy = (h - screenH) / 2
        map = (p) => ({ x: ox + p.x * scale, y: oy + p.y * scale })
      }

      if (path.length > 1 && times.length) {
        const lastT = times.at(-1) ?? timeMs
        const ratio = lastT > 0 ? Math.min(1, timeMs / lastT) : 0
        const endIdx = Math.max(1, Math.round(ratio * (path.length - 1)))
        const mapped = path.slice(0, endIdx + 1).map(map)
        if (mapped.length > 1) {
          ctx.strokeStyle = 'rgba(112,169,29,0.75)'
          ctx.lineWidth = 2.5
          ctx.lineJoin = 'round'
          ctx.lineCap = 'round'
          ctx.beginPath()
          ctx.moveTo(mapped[0]!.x, mapped[0]!.y)
          for (let i = 1; i < mapped.length; i++) ctx.lineTo(mapped[i]!.x, mapped[i]!.y)
          ctx.stroke()
        }
      }

      for (const click of clicks) {
        if (click.t > timeMs) continue
        const p = map({ x: click.x, y: click.y })
        const age = (timeMs - click.t) / 1000
        const radius = 6 + Math.min(20, age * 14)
        const alpha = Math.max(0, 0.55 - age * 0.4)
        ctx.strokeStyle = `rgba(255,92,53,${alpha})`
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
        ctx.stroke()
      }

      const lastScroll = [...scrolls].reverse().find((s) => s.t <= timeMs)
      if (lastScroll && timeMs - lastScroll.t < 1200 && layout) {
        ctx.fillStyle = 'rgba(23,29,27,0.75)'
        ctx.fillRect(layout.left + layout.width - 72, layout.top + 8, 64, 22)
        ctx.fillStyle = '#dff0c8'
        ctx.font = '11px system-ui,sans-serif'
        ctx.fillText('↕ scroll', layout.left + layout.width - 66, layout.top + 23)
      }

      const cursor = positionAtTime(times, path, timeMs)
      if (cursor) {
        const p = map(cursor)
        ctx.fillStyle = '#70a91d'
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.arc(p.x, p.y, 8, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
      }
    }

    draw()
    const ro = new ResizeObserver(draw)
    ro.observe(parent)
    return () => ro.disconnect()
  }, [times, path, clicks, scrolls, timeMs, viewport, layout])

  return <canvas ref={canvasRef} className="bf-interaction-overlay" aria-hidden />
}
