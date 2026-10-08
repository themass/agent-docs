import assert from 'node:assert/strict'

import { formatSessionReuse, type TraceRecord } from '@naviforge/session'

function noteRecord(id: string, text: string, topic?: string): TraceRecord {
  return {
    schema: 1,
    id,
    at: Number(id.replace(/\D/g, '')) || 1,
    runId: 'run-1',
    channel: 'trace',
    type: 'run.note',
    payload: { text, topic },
  } as TraceRecord
}

// --- Regression for tests/message.txt drift: once PreflightHook has
// emitted a structured DELIVERABLE marker, formatSessionReuse must surface
// it as `lastDeliverable` so the next run in the thread can stay sticky.
{
  const records: TraceRecord[] = [
    noteRecord('n1', 'DELIVERABLE: media', 'deliverable'),
    noteRecord('n2', 'some unrelated internal note', 'internal'),
  ]
  const reuse = formatSessionReuse(records)
  assert.equal(reuse.lastDeliverable, 'media')
}

// --- Most recent DELIVERABLE marker wins when a thread has had multiple
// runs (each run emits its own marker; later ones must override earlier).
{
  const records: TraceRecord[] = [
    noteRecord('n1', 'DELIVERABLE: media', 'deliverable'),
    noteRecord('n2', 'DELIVERABLE: script', 'deliverable'),
  ]
  const reuse = formatSessionReuse(records)
  assert.equal(reuse.lastDeliverable, 'script')
}

// --- No deliverable marker at all (fresh thread / older trace) must not
// throw and must leave lastDeliverable undefined.
{
  const records: TraceRecord[] = [noteRecord('n1', 'PREFLIGHT: something', 'internal')]
  const reuse = formatSessionReuse(records)
  assert.equal(reuse.lastDeliverable, undefined)
}

console.log('thread-context self-check ok')
