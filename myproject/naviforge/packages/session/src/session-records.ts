import type { SessionSnapshot, TraceRecord } from './types.js'

export function sortSessionsByRecent(sessions: SessionSnapshot[]): SessionSnapshot[] {
  return [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)
}

function pinnedSessionRecords(records: TraceRecord[]): TraceRecord[] {
  const pinned = records.filter(
    (record) => record.type === 'run.context' || record.type === 'run.tools' || record.type === 'user.task'
  )
  const lastContext = records.filter((record) => record.type === 'metrics.context').at(-1)
  const lastTokens = records.filter((record) => record.type === 'metrics.tokens').at(-1)
  return [...pinned, ...(lastContext ? [lastContext] : []), ...(lastTokens ? [lastTokens] : [])]
}

export function capSessionRecords(records: TraceRecord[], max = 240): TraceRecord[] {
  if (records.length <= max) return records
  const pinned = pinnedSessionRecords(records)
  const pinnedIds = new Set(pinned.map((record) => record.id))
  const rest = records.filter((record) => !pinnedIds.has(record.id))
  const retained = [
    ...pinned,
    ...rest.filter((record) => record.channel !== 'telemetry').slice(-max + pinned.length),
  ]
  const retainedIds = new Set(retained.map((record) => record.id))
  return records.filter((record) => retainedIds.has(record.id))
}

/** Preserve the first instance of a record ID (background is sole ID authority). */
export function appendUniqueRecords(
  current: TraceRecord[],
  record: TraceRecord,
  limit = 200
): TraceRecord[] {
  return current.some((item) => item.id === record.id)
    ? current
    : capSessionRecords([...current, record], limit)
}

export function redactSessionText(value: string, max = 4_000): string {
  return value
    .replace(/(authorization\s*:\s*bearer\s+)[^\s,;]+/gi, '$1[REDACTED]')
    .replace(/\b(sk|api)[-_][A-Za-z0-9_-]{12,}\b/gi, '[REDACTED]')
    .slice(0, max)
}
