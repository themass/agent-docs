import { safeStorageLocalGet, safeStorageLocalSet } from './extension-runtime'

const ROOT_ID = 'naviforge-video-subs'
const POS_KEY = 'naviforgeSubtitlePos'

export type OverlayCue = { start: number; end: number; text: string; translated: string }

function cueAt(cues: OverlayCue[], time: number): OverlayCue | null {
  let lo = 0
  let hi = cues.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (cues[mid]!.start <= time) {
      found = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  if (found < 0) return null
  const cue = cues[found]!
  return time < cue.end ? cue : null
}

function findVideo(): HTMLVideoElement | null {
  return document.querySelector(
    'video.html5-main-video, video.bpx-player-video-element, video'
  )
}

function overlayHost(video: HTMLVideoElement): HTMLElement {
  const fs = document.fullscreenElement
  if (fs instanceof HTMLElement) return fs
  return (
    video.closest(
      '#movie_player, .html5-video-player, .bpx-player-container, .bpx-player-video-area'
    ) ??
    video.parentElement ??
    document.body
  )
}

let teardown: (() => void) | null = null

export function videoSubtitleActive(): boolean {
  return Boolean(teardown)
}

export function stopVideoSubtitles(): void {
  teardown?.()
  teardown = null
}

export function startVideoSubtitles(cues: OverlayCue[]): { success: boolean; error?: string } {
  stopVideoSubtitles()
  if (!cues.length) return { success: false, error: '没有字幕' }
  const video0 = findVideo()
  if (!video0) return { success: false, error: '当前页没有视频' }

  const root = document.createElement('div')
  root.id = ROOT_ID
  const shadow = root.attachShadow({ mode: 'open' })
  shadow.innerHTML = `
    <style>
      :host { all: initial; }
      .box {
        position: absolute;
        left: 50%;
        top: 82%;
        z-index: 2147483646;
        width: min(90%, 42rem);
        transform: translate(-50%, -50%);
        padding: 8px 14px 10px;
        border-radius: 10px;
        background: rgb(0 0 0 / 0.55);
        color: #fff;
        font: 16px/1.45 system-ui, sans-serif;
        text-align: center;
        cursor: grab;
        user-select: none;
        text-shadow: 0 1px 2px rgb(0 0 0 / 0.8);
        backdrop-filter: blur(8px);
      }
      .box:active { cursor: grabbing; }
      .origin { font-size: 12px; line-height: 1.35; color: rgb(255 255 255 / 0.72); }
      .zh { margin-top: 2px; font-size: 18px; font-weight: 600; }
      .hint { margin-top: 4px; font-size: 10px; color: rgb(255 255 255 / 0.4); }
    </style>
    <div class="box" part="box">
      <div class="origin"></div>
      <div class="zh"></div>
      <div class="hint">拖动调整位置</div>
    </div>
  `
  const box = shadow.querySelector('.box') as HTMLElement
  const originEl = shadow.querySelector('.origin') as HTMLElement
  const zhEl = shadow.querySelector('.zh') as HTMLElement
  const hintEl = shadow.querySelector('.hint') as HTMLElement
  let x = 0.5
  let y = 0.82
  let host: HTMLElement | null = null
  let lastKey = ''
  let hintTimer = 0

  void safeStorageLocalGet(POS_KEY).then((saved) => {
    const pos = saved?.[POS_KEY] as { x?: number; y?: number } | undefined
    if (typeof pos?.x === 'number') x = pos.x
    if (typeof pos?.y === 'number') y = pos.y
    applyPos()
  })

  function mount(): void {
    const video = findVideo()
    if (!video) return
    const next = overlayHost(video)
    if (host === next && next.contains(root)) return
    host = next
    const style = getComputedStyle(next)
    if (style.position === 'static') next.style.position = 'relative'
    next.appendChild(root)
    applyPos()
  }

  function applyPos(): void {
    box.style.left = `${x * 100}%`
    box.style.top = `${y * 100}%`
  }

  function paint(): void {
    const video = findVideo()
    if (!video) return
    mount()
    const cue = cueAt(cues, video.currentTime)
    const key = cue ? `${cue.start}:${cue.translated}` : ''
    if (key === lastKey) return
    lastKey = key
    if (!cue) {
      originEl.textContent = ''
      zhEl.textContent = ''
      return
    }
    originEl.textContent = cue.translated === cue.text ? '' : cue.text
    zhEl.textContent = cue.translated
  }

  function onPointerDown(event: PointerEvent): void {
    if (event.button !== 0 || !host) return
    event.preventDefault()
    event.stopPropagation()
    box.setPointerCapture(event.pointerId)
    const rect = host.getBoundingClientRect()
    const onMove = (move: PointerEvent) => {
      if (!host) return
      x = Math.min(0.92, Math.max(0.08, (move.clientX - rect.left) / Math.max(rect.width, 1)))
      y = Math.min(0.92, Math.max(0.08, (move.clientY - rect.top) / Math.max(rect.height, 1)))
      applyPos()
    }
    const onUp = () => {
      box.releasePointerCapture(event.pointerId)
      box.removeEventListener('pointermove', onMove)
      box.removeEventListener('pointerup', onUp)
      void safeStorageLocalSet({ [POS_KEY]: { x, y } })
    }
    box.addEventListener('pointermove', onMove)
    box.addEventListener('pointerup', onUp)
  }

  box.addEventListener('pointerdown', onPointerDown)
  document.addEventListener('fullscreenchange', mount)
  const video = findVideo()
  video?.addEventListener('timeupdate', paint)
  const tick = window.setInterval(paint, 250)
  hintTimer = window.setTimeout(() => {
    hintEl.remove()
  }, 4000)
  mount()
  paint()

  teardown = () => {
    window.clearInterval(tick)
    window.clearTimeout(hintTimer)
    document.removeEventListener('fullscreenchange', mount)
    findVideo()?.removeEventListener('timeupdate', paint)
    box.removeEventListener('pointerdown', onPointerDown)
    root.remove()
  }
  return { success: true }
}

export function handleVideoSubtitleMessage(payload: {
  op?: string
  cues?: OverlayCue[]
}): { success: boolean; active?: boolean; error?: string } {
  if (payload.op === 'status') return { success: true, active: videoSubtitleActive() }
  if (payload.op === 'stop') {
    stopVideoSubtitles()
    return { success: true, active: false }
  }
  if (payload.op === 'start') {
    const started = startVideoSubtitles(payload.cues ?? [])
    return { ...started, active: started.success }
  }
  return { success: false, error: 'unknown subtitle op' }
}
