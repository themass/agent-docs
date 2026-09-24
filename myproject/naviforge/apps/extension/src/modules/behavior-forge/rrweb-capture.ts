import { record, type eventWithTime } from 'rrweb'

const MAX_BUFFER = 24
const FLUSH_MS = 600

type CaptureHandle = { stop: () => void }

let active: CaptureHandle | null = null

/** DOM replay capture via rrweb — runs alongside pointer-trail capture. */
export function startRrwebCapture(
  sessionId: string,
  onBatch: (events: eventWithTime[]) => void
): () => void {
  active?.stop()
  const buffer: eventWithTime[] = []
  let lastFlush = performance.now()
  let flushTimer: number | null = null

  const flush = () => {
    if (!buffer.length) return
    onBatch(buffer.splice(0, buffer.length))
    lastFlush = performance.now()
  }

  const scheduleFlush = () => {
    if (flushTimer != null) return
    flushTimer = window.setTimeout(() => {
      flushTimer = null
      flush()
    }, FLUSH_MS)
  }

  const onPageHide = () => flush()
  window.addEventListener('pagehide', onPageHide, { capture: true })

  const stopRecord = record({
    emit(event) {
      buffer.push(event)
      if (buffer.length >= MAX_BUFFER || performance.now() - lastFlush > FLUSH_MS) {
        flush()
        return
      }
      scheduleFlush()
    },
    checkoutEveryNms: 15_000,
    maskAllInputs: true,
    maskTextSelector: '[data-nf-sensitive], [type="password"]',
    recordCanvas: false,
    sampling: {
      mousemove: 60,
      mouseInteraction: true,
      scroll: 150,
      input: 'last',
    },
  })

  const stop = () => {
    window.removeEventListener('pagehide', onPageHide, true)
    if (flushTimer != null) window.clearTimeout(flushTimer)
    stopRecord?.()
    flush()
    if (active?.stop === stop) active = null
    void sessionId
  }

  active = { stop }
  return stop
}

export function stopRrwebCapture(): void {
  active?.stop()
  active = null
}
