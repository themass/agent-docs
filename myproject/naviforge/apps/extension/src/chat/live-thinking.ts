import type { TraceRecord } from '@naviforge/session'

export const LIVE_FEED_MAX = 80

export function clipLiveLine(text: string, max = 120): string {
  const trimmed = text.replace(/\s+/g, ' ').trim()
  if (!trimmed) return ''
  return trimmed.length <= max ? trimmed : `${trimmed.slice(0, max - 1)}…`
}

/** Append a line to the rolling activity feed (dedupe consecutive repeats). */
export function pushLiveFeed(prev: string[], line: string): string[] {
  const next = clipLiveLine(line)
  if (!next || prev[prev.length - 1] === next) return prev
  const merged = [...prev, next]
  return merged.length > LIVE_FEED_MAX ? merged.slice(-LIVE_FEED_MAX) : merged
}

/** Latest model reasoning snippet for the thinking chip. */
export function latestReasoning(records: readonly TraceRecord[]): string | null {
  for (let i = records.length - 1; i >= 0; i--) {
    const record = records[i]
    if (record.type !== 'model.turn') continue
    const raw = record.payload.io?.reasoning
    if (typeof raw !== 'string') continue
    const clipped = clipLiveLine(raw, 160)
    if (clipped) return clipped
  }
  return null
}

/** Avoid showing a finished-tool line in the header while the run is still active. */
export function headerStatusDetail(busy: boolean, detail: string | null | undefined): string | null {
  const text = detail?.trim()
  if (!text) return null
  if (busy && (/^已完成：/.test(text) || /^工具失败：/.test(text))) return '继续执行…'
  return text
}
