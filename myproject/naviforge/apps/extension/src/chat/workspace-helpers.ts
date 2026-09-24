import { validateTraceRecord, type TraceRecord } from '@naviforge/session'

import type { RecordView } from '../lib/agent-event-projection'
import type { ListResultItem } from '../lib/list-result-format'

export const DEFAULT_LLM = {
  baseURL: 'https://newapi.yuaiweiwu.com/v1',
  model: 'mt-claude-sonnet-4-6',
  apiKey: '',
}

/** ponytail: skip thumb RPCs after one stale-host miss; reset when Host is reinstalled. */
export let shotThumbsAvailable: boolean | null = null

export function setShotThumbsAvailable(value: boolean | null): void {
  shotThumbsAvailable = value
}

export type TopVideo = ListResultItem & {
  label: string
  index: number
  title: string
}

export type PickedElement = {
  selector?: string
  title?: string
  tag?: string
  text?: string
}

export function pickedLabel(element: PickedElement): string {
  return element.title || element.text || element.tag || '选中元素'
}

export function asLedger(raw: unknown): TraceRecord[] {
  if (!Array.isArray(raw)) return []
  return raw.flatMap((item) => {
    try {
      return [validateTraceRecord(item)]
    } catch {
      return []
    }
  })
}

export function exportSessionMarkdown(
  events: RecordView[],
  task: string,
  model?: string
): string {
  const lines = [`# NaviForge Session`, ``, `**Task:** ${task}`, model ? `**Model:** ${model}` : '', ``]
  for (const event of events) {
    lines.push(`- [${event.variant}] ${event.body}`)
  }
  return lines.filter(Boolean).join('\n')
}
