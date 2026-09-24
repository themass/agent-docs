const ROOT_ID = 'naviforge-behavior-live-overlay'
const STYLE_ID = 'naviforge-behavior-live-overlay-style'

type Ripple = { x: number; y: number; born: number }
type TrailPoint = { x: number; y: number }

let raf = 0
let cursor = { x: -100, y: -100 }
let trail: TrailPoint[] = []
let ripples: Ripple[] = []
let scrollFlash = 0

function ensureStyles(): void {
  if (document.getElementById(STYLE_ID)) return
  const style = document.createElement('style')
  style.id = STYLE_ID
  style.textContent = `
    #${ROOT_ID} {
      position: fixed; inset: 0; z-index: 2147483644;
      pointer-events: none; overflow: hidden;
    }
    #${ROOT_ID} canvas { width: 100%; height: 100%; display: block; }
    #${ROOT_ID} [data-nf-scroll-flash] {
      position: fixed; right: 16px; bottom: 88px;
      padding: 6px 10px; border-radius: 8px;
      background: rgba(23,29,27,.82); color: #dff0c8;
      font: 11px/1.2 system-ui,sans-serif; opacity: 0;
      transition: opacity .2s ease;
    }
    #${ROOT_ID} [data-nf-scroll-flash].on { opacity: 1; }
  `
  document.head.appendChild(style)
}

function draw(): void {
  const root = document.getElementById(ROOT_ID)
  const canvas = root?.querySelector('canvas') as HTMLCanvasElement | null
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width / devicePixelRatio
  const h = canvas.height / devicePixelRatio
  ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0)
  ctx.clearRect(0, 0, w, h)

  const now = performance.now()

  if (trail.length > 1) {
    ctx.strokeStyle = 'rgba(112,169,29,0.55)'
    ctx.lineWidth = 2
    ctx.lineJoin = 'round'
    ctx.lineCap = 'round'
    ctx.beginPath()
    ctx.moveTo(trail[0]!.x, trail[0]!.y)
    for (let i = 1; i < trail.length; i++) ctx.lineTo(trail[i]!.x, trail[i]!.y)
    ctx.stroke()
  }

  for (const r of ripples) {
    const age = (now - r.born) / 1000
    if (age > 1.2) continue
    const radius = 8 + age * 28
    const alpha = Math.max(0, 0.55 - age * 0.45)
    ctx.strokeStyle = `rgba(255,92,53,${alpha})`
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(r.x, r.y, radius, 0, Math.PI * 2)
    ctx.stroke()
  }
  ripples = ripples.filter((r) => now - r.born < 1200)

  if (cursor.x >= 0) {
    ctx.fillStyle = '#70a91d'
    ctx.strokeStyle = '#171d1b'
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.arc(cursor.x, cursor.y, 7, 0, Math.PI * 2)
    ctx.fill()
    ctx.stroke()
    ctx.fillStyle = 'rgba(112,169,29,0.22)'
    ctx.beginPath()
    ctx.arc(cursor.x, cursor.y, 14, 0, Math.PI * 2)
    ctx.fill()
  }

  raf = requestAnimationFrame(draw)
}

function resize(canvas: HTMLCanvasElement): void {
  const rect = canvas.getBoundingClientRect()
  canvas.width = Math.max(1, rect.width * devicePixelRatio)
  canvas.height = Math.max(1, rect.height * devicePixelRatio)
}

export function startRecordingLiveOverlay(): () => void {
  stopRecordingLiveOverlay()
  ensureStyles()

  const root = document.createElement('div')
  root.id = ROOT_ID
  root.innerHTML = `
    <canvas aria-hidden="true"></canvas>
    <div data-nf-scroll-flash>↕ 滚动</div>
  `
  document.documentElement.append(root)

  const canvas = root.querySelector('canvas')!
  resize(canvas)
  const ro = new ResizeObserver(() => resize(canvas))
  ro.observe(root)

  const onMove = (e: PointerEvent) => {
    cursor = { x: e.clientX, y: e.clientY }
    const last = trail.at(-1)
    if (!last || (last.x - e.clientX) ** 2 + (last.y - e.clientY) ** 2 > 16) {
      trail.push({ x: e.clientX, y: e.clientY })
      if (trail.length > 48) trail.shift()
    }
  }

  const onClick = (e: MouseEvent) => {
    ripples.push({ x: e.clientX, y: e.clientY, born: performance.now() })
  }

  const flashEl = root.querySelector('[data-nf-scroll-flash]') as HTMLElement
  let scrollTimer: number | null = null
  const onScroll = () => {
    scrollFlash++
    flashEl.classList.add('on')
    if (scrollTimer != null) window.clearTimeout(scrollTimer)
    scrollTimer = window.setTimeout(() => flashEl.classList.remove('on'), 600)
  }

  window.addEventListener('pointermove', onMove, { passive: true, capture: true })
  window.addEventListener('click', onClick, { capture: true })
  window.addEventListener('scroll', onScroll, { passive: true, capture: true })

  raf = requestAnimationFrame(draw)

  return () => {
    window.removeEventListener('pointermove', onMove, true)
    window.removeEventListener('click', onClick, true)
    window.removeEventListener('scroll', onScroll, true)
    ro.disconnect()
    if (scrollTimer != null) window.clearTimeout(scrollTimer)
    cancelAnimationFrame(raf)
    root.remove()
    trail = []
    ripples = []
    cursor = { x: -100, y: -100 }
  }
}

export function stopRecordingLiveOverlay(): void {
  document.getElementById(ROOT_ID)?.remove()
  cancelAnimationFrame(raf)
}
