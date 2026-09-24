import type { BehaviorEvent } from './types.js'

const MIN_MOVE_PX = 4

type CaptureHandle = { stop: () => void }

let active: CaptureHandle | null = null

function nowMs(pageStarted: number, offset: number): number {
  return offset + Math.round(performance.now() - pageStarted)
}

function safeTag(el: EventTarget | null): string | undefined {
  if (!(el instanceof Element)) return undefined
  const tag = el.tagName.toLowerCase()
  const id = el.id ? `#${el.id}` : ''
  const cls =
    el.classList.length > 0
      ? `.${[...el.classList].slice(0, 2).join('.')}`
      : ''
  return `${tag}${id}${cls}`.slice(0, 80)
}

/** Start passive capture on this page. Returns teardown. */
export function startBehaviorCapture(
  sessionId: string,
  onBatch: (events: BehaviorEvent[]) => void,
  opts?: { pointerThrottleMs?: number; idleThresholdMs?: number; timeOffsetMs?: number }
): () => void {
  active?.stop()
  const pointerThrottleMs = opts?.pointerThrottleMs ?? 80
  const idleThresholdMs = opts?.idleThresholdMs ?? 5000
  const timeOffsetMs = Math.max(0, opts?.timeOffsetMs ?? 0)
  const started = performance.now()
  const buffer: BehaviorEvent[] = []
  let lastFlush = performance.now()
  let lastPointerAt = performance.now()
  let lastMove = { x: 0, y: 0 }
  let idleSince: number | null = null

  const flush = () => {
    if (!buffer.length) return
    onBatch(buffer.splice(0, buffer.length))
    lastFlush = performance.now()
  }

  const push = (event: BehaviorEvent) => {
    buffer.push(event)
    if (buffer.length >= 40 || performance.now() - lastFlush > 500) flush()
  }

  push({
    t: timeOffsetMs,
    kind: 'viewport',
    w: window.innerWidth,
    h: window.innerHeight,
    dpr: window.devicePixelRatio || 1,
  })
  push({ t: timeOffsetMs, kind: 'nav', url: location.href, title: document.title })

  const onPointerMove = (e: PointerEvent) => {
    const t = nowMs(started, timeOffsetMs)
    const dx = e.clientX - lastMove.x
    const dy = e.clientY - lastMove.y
    if (dx * dx + dy * dy < MIN_MOVE_PX * MIN_MOVE_PX) return
    lastMove = { x: e.clientX, y: e.clientY }
    lastPointerAt = performance.now()
    if (idleSince != null) {
      push({ t, kind: 'idle', durationMs: Math.round(lastPointerAt - idleSince) })
      idleSince = null
    }
    push({ t, kind: 'pointer', x: e.clientX, y: e.clientY })
  }

  let pointerTimer: number | null = null
  const throttledPointer = (e: PointerEvent) => {
    if (pointerTimer != null) return
    pointerTimer = window.setTimeout(() => {
      pointerTimer = null
      onPointerMove(e)
    }, pointerThrottleMs)
  }

  const onClick = (e: MouseEvent) => {
    push({
      t: nowMs(started, timeOffsetMs),
      kind: 'click',
      x: e.clientX,
      y: e.clientY,
      button: e.button,
      tag: safeTag(e.target),
    })
    lastPointerAt = performance.now()
  }

  let scrollTimer: number | null = null
  const onScroll = () => {
    if (scrollTimer != null) return
    scrollTimer = window.setTimeout(() => {
      scrollTimer = null
      push({
        t: nowMs(started, timeOffsetMs),
        kind: 'scroll',
        scrollX: window.scrollX,
        scrollY: window.scrollY,
      })
    }, 200)
  }

  const onKey = (e: KeyboardEvent) => {
    if (e.key.length > 1 && !['Enter', 'Escape', 'Tab', 'Backspace'].includes(e.key)) return
    push({
      t: nowMs(started, timeOffsetMs),
      kind: 'key',
      key: e.key,
      meta: e.metaKey || e.ctrlKey,
    })
  }

  const onNav = () => {
    push({ t: nowMs(started, timeOffsetMs), kind: 'nav', url: location.href, title: document.title })
  }

  const idleTick = window.setInterval(() => {
    if (performance.now() - lastPointerAt < idleThresholdMs) return
    if (idleSince == null) idleSince = performance.now()
  }, 1000)

  window.addEventListener('pointermove', throttledPointer, { passive: true, capture: true })
  window.addEventListener('click', onClick, { capture: true })
  window.addEventListener('scroll', onScroll, { passive: true, capture: true })
  window.addEventListener('keydown', onKey, { capture: true })
  window.addEventListener('popstate', onNav)
  window.addEventListener('hashchange', onNav)
  const onPageHide = () => flush()
  window.addEventListener('pagehide', onPageHide, { capture: true })

  const origPush = history.pushState.bind(history)
  const origReplace = history.replaceState.bind(history)
  history.pushState = (...args) => {
    origPush(...args)
    onNav()
  }
  history.replaceState = (...args) => {
    origReplace(...args)
    onNav()
  }

  const stop = () => {
    window.clearInterval(idleTick)
    if (pointerTimer != null) window.clearTimeout(pointerTimer)
    if (scrollTimer != null) window.clearTimeout(scrollTimer)
    window.removeEventListener('pointermove', throttledPointer, true)
    window.removeEventListener('click', onClick, true)
    window.removeEventListener('scroll', onScroll, true)
    window.removeEventListener('keydown', onKey, true)
    window.removeEventListener('popstate', onNav)
    window.removeEventListener('hashchange', onNav)
    window.removeEventListener('pagehide', onPageHide, true)
    history.pushState = origPush
    history.replaceState = origReplace
    flush()
    if (active?.stop === stop) active = null
    void sessionId
  }

  active = { stop }
  return stop
}

export function stopBehaviorCapture(): void {
  active?.stop()
  active = null
}
