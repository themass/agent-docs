import type { TraceRecord } from '@naviforge/session'

function clip(text: string, max: number): string {
  const trimmed = text.replace(/\s+/g, ' ').trim()
  if (!trimmed) return ''
  return trimmed.length <= max ? trimmed : `${trimmed.slice(0, max - 1)}…`
}

/** One-line parent UI feed from an isolated leaf trace record. */
export function leafProgressLine(record: TraceRecord): string | null {
  if (record.type === 'model.turn') {
    const tool = record.payload.call?.tool
    if (tool) return `子任务 · ${tool}`
    const summary = record.payload.summary?.trim()
    if (summary) return `子任务 · ${clip(summary, 100)}`
  }
  if (record.type === 'tool.result') {
    const tool = record.payload.tool
    if (record.payload.ok) return `子任务 · ${tool} 完成`
    const msg = record.payload.error?.message ?? 'failed'
    return `子任务 · ${tool} 失败: ${clip(msg, 80)}`
  }
  if (record.type === 'run.error') {
    return `子任务 · ${clip(record.payload.message, 100)}`
  }
  if (record.type === 'run.result') {
    return '子任务 · 完成'
  }
  return null
}
