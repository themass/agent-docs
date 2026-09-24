/** Stable key order so a copied JSONL line is readable. Still one object per line. */
const JSONL_KEY_ORDER = [
  'schema',
  'record',
  'id',
  'at',
  'runId',
  'taskId',
  'step',
  'turn',
  'channel',
  'type',
  'payload',
  'title',
  'task',
  'status',
  'kind',
  'exportedAt',
] as const

export function orderJsonlValue(value: unknown): unknown {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return value
  const rec = value as Record<string, unknown>
  const out: Record<string, unknown> = {}
  for (const key of JSONL_KEY_ORDER) {
    if (rec[key] !== undefined) out[key] = rec[key]
  }
  for (const key of Object.keys(rec).sort()) {
    if (!(key in out) && rec[key] !== undefined) out[key] = rec[key]
  }
  return out
}

/** NDJSON: compact JSON, no pretty-print (inner newlines would break the format). */
export function stringifyJsonl(value: unknown): string {
  return JSON.stringify(orderJsonlValue(value)).replace(/\u2028|\u2029/g, '')
}

/** One ledger line for append-only JSONL files (includes trailing newline). */
export function stringifyJsonlLine(value: unknown): string {
  return `${stringifyJsonl(value)}\n`
}
