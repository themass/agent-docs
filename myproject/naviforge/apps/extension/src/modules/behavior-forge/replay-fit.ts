/** Layout of the scaled rrweb player inside the stage (for pointer overlay alignment). */
export type ReplayLayout = {
  /** Recorded viewport width (window.innerWidth). */
  viewW: number
  /** Recorded viewport height (window.innerHeight). */
  viewH: number
  /** Wrapper position relative to stage top-left. */
  left: number
  top: number
  width: number
  height: number
}

/** Scale rrweb `.replayer-wrapper` to fit a stage while keeping aspect ratio. */
export function fitRrwebWrapper(
  stage: HTMLElement,
  host: HTMLElement,
  meta: { width: number; height: number },
  viewport?: { w: number; h: number }
): ReplayLayout | null {
  const wrapper = host.querySelector('.replayer-wrapper') as HTMLElement | null
  if (!wrapper || !meta.width || !meta.height) return null

  const viewW = viewport?.w && viewport.w > 0 ? viewport.w : meta.width
  const viewH = viewport?.h && viewport.h > 0 ? viewport.h : meta.height

  const pad = 12
  const availW = Math.max(120, stage.clientWidth - pad * 2)
  const availH = Math.max(120, stage.clientHeight - pad * 2)
  // Fit to what the user actually saw (viewport), not oversized document snapshots.
  const fitW = Math.min(meta.width, viewW)
  const fitH = Math.min(meta.height, viewH)
  const scale = Math.min(availW / fitW, availH / fitH, 1)

  wrapper.style.width = `${meta.width}px`
  wrapper.style.height = `${meta.height}px`
  wrapper.style.transform = `scale(${scale})`
  wrapper.style.transformOrigin = 'top center'
  wrapper.style.margin = '0 auto'

  const scaledH = meta.height * scale
  host.style.display = 'flex'
  host.style.justifyContent = 'center'
  host.style.alignItems = 'flex-start'
  host.style.width = '100%'
  host.style.height = `${scaledH}px`
  host.style.minHeight = '0'
  host.style.overflow = 'visible'

  const wr = wrapper.getBoundingClientRect()
  const sr = stage.getBoundingClientRect()

  return {
    viewW,
    viewH,
    left: wr.left - sr.left,
    top: wr.top - sr.top,
    width: wr.width,
    height: wr.height,
  }
}
