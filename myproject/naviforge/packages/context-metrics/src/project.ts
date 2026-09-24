import type { ContextBreakdown } from './types.js'

/** Read latest telemetry breakdown from audit records (UI projector). */
export function latestContextBreakdown(
  records: ReadonlyArray<{ type: string; payload: unknown }>
): ContextBreakdown | null {
  for (let i = records.length - 1; i >= 0; i--) {
    const record = records[i]
    if (record?.type !== 'metrics.context') continue
    const payload = record.payload as { breakdown?: ContextBreakdown }
    if (payload?.breakdown) return payload.breakdown
  }
  return null
}
