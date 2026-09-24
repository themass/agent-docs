import {
  slicePlan,
  stitchFullPage,
  type CaptureSlice,
  type PageMetrics,
} from './capture-full-page'

type MetricsResponse = PageMetrics & { success: boolean; error?: string }

export type FullPageCaptureResult = {
  dataUrl: string
  width: number
  height: number
  slices: number
}

type SendFn = <T>(tabId: number, action: string, payload?: Record<string, unknown>) => Promise<T>

/** Scroll the tab, capture each viewport slice, stitch into one PNG. */
export async function captureFullPageTab(
  tabId: number,
  windowId: number,
  send: SendFn,
  captureVisible: (windowId: number) => Promise<string>
): Promise<FullPageCaptureResult> {
  const metrics = await send<MetricsResponse>(tabId, 'screenshot_metrics')
  if (!metrics?.success) throw new Error(metrics?.error ?? 'screenshot_metrics failed')

  const startY = metrics.scrollY
  const positions = slicePlan(metrics)
  const slices: CaptureSlice[] = []

  for (const y of positions) {
    await send(tabId, 'scroll_to_y', { y, behavior: 'instant' })
    const dataUrl = await captureVisible(windowId)
    slices.push({ dataUrl, scrollY: y })
  }

  await send(tabId, 'scroll_to_y', { y: startY, behavior: 'instant' })
  const stitched = await stitchFullPage(slices, metrics)
  return { ...stitched, slices: slices.length }
}
