import { stringifyJsonl } from './jsonl.js'
import {
  TRACE_SCHEMA,
  type TraceChannel,
  type TraceRecord,
  type TraceRecordPayload,
  type TraceRecordType,
} from './types.js'

export const TRACE_CHANNEL: Record<TraceRecordType, TraceChannel> = {
  'user.task': 'conversation',
  'user.steer': 'conversation',
  'run.result': 'conversation',
  'run.ask': 'conversation',
  'run.context': 'trace',
  'run.tools': 'trace',
  'run.mode': 'trace',
  'model.turn': 'trace',
  'tool.result': 'trace',
  'run.recovery': 'trace',
  'run.error': 'trace',
  'run.network': 'trace',
  'run.note': 'trace',
  'context.compaction': 'trace',
  'run.log': 'telemetry',
  'metrics.tokens': 'telemetry',
  'metrics.context': 'telemetry',
  'intake.question': 'conversation',
  'intake.answer': 'conversation',
  'intake.complete': 'trace',
  'artifact.saved': 'trace',
}

export function createTraceRecord<Type extends TraceRecordType>(
  input: {
    type: Type
    payload: TraceRecordPayload[Type]
    runId: string
    parentRunId?: string
    taskId?: string
    turn?: number
  }
): TraceRecord {
  return validateTraceRecord({
    ...input,
    schema: TRACE_SCHEMA,
    id: crypto.randomUUID(),
    at: Date.now(),
    channel: TRACE_CHANNEL[input.type],
  })
}

/** Reject malformed records at the JSON boundary without translating old schemas. */
export function validateTraceRecord(value: unknown): TraceRecord {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('TraceRecord must be an object')
  const record = value as Partial<TraceRecord>
  if ('record' in record) throw new TypeError('TraceRecord has unexpected field "record"')
  if (record.schema !== TRACE_SCHEMA) throw new TypeError('TraceRecord schema must be 1')
  if (typeof record.id !== 'string' || !record.id) throw new TypeError('TraceRecord id is required')
  if (!Number.isFinite(record.at)) throw new TypeError('TraceRecord at must be finite')
  if (typeof record.runId !== 'string' || !record.runId) throw new TypeError('TraceRecord runId is required')
  if (!(typeof record.type === 'string' && record.type in TRACE_CHANNEL)) throw new TypeError('TraceRecord type is invalid')
  if (record.channel !== TRACE_CHANNEL[record.type as TraceRecordType]) {
    throw new TypeError('TraceRecord channel must match type')
  }
  if (!record.payload || typeof record.payload !== 'object') throw new TypeError('TraceRecord payload is required')
  return record as TraceRecord
}

/** Serialize canonical records as JSONL; caller controls any telemetry filtering. */
export function formatAuditJsonl(records: readonly TraceRecord[], opts?: { includeTelemetry?: boolean }): string {
  return records
    .filter((record) => opts?.includeTelemetry || record.channel !== 'telemetry')
    .map((record) => stringifyJsonl(validateTraceRecord(record)))
    .join('\n')
}

export type { TraceRecordPayload }
