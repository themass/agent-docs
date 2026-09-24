import type { TraceRecord } from './types.js'

const CONTINUATION_RE =
  /^(继续|接着|再来|重试|resume|retry|continue|go\s*on)([。.\s!！?？…]*)?$/i

function userTaskText(record: TraceRecord): string | undefined {
  if (record.type !== 'user.task') return undefined
  const text = typeof record.payload.text === 'string' ? record.payload.text.trim() : ''
  return text || undefined
}

/** User typed a resume/continue cue instead of stating a new goal. */
export function isContinuationMessage(text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return false
  return CONTINUATION_RE.test(trimmed)
}

/** First non-continuation user.task — used for session/thread display titles only. */
export function extractOriginalTaskFromRecords(records: TraceRecord[]): string | undefined {
  for (const record of records) {
    const text = userTaskText(record)
    if (text && !isContinuationMessage(text)) return text
  }
  return undefined
}

/** Display title: keep first goal; follow-ups like「继续」must not rename the session. */
export function sessionDisplayTitle(input: string, priorRecords: TraceRecord[]): string {
  if (!isContinuationMessage(input.trim())) return input.trim()
  return extractOriginalTaskFromRecords(priorRecords) ?? input.trim()
}
