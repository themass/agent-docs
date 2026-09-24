import assert from 'node:assert/strict'
import { validateTraceRecord, appendUniqueRecords } from '@naviforge/session'

const one = validateTraceRecord({
  schema: 1,
  id: 'one',
  at: 1,
  runId: 'run',
  channel: 'conversation',
  type: 'run.result',
  payload: { text: 'one' },
})
const two = validateTraceRecord({
  schema: 1,
  id: 'two',
  at: 2,
  runId: 'run',
  channel: 'conversation',
  type: 'run.result',
  payload: { text: 'two' },
})
const three = validateTraceRecord({
  schema: 1,
  id: 'three',
  at: 3,
  runId: 'run',
  channel: 'conversation',
  type: 'run.result',
  payload: { text: 'three' },
})

assert.deepEqual(appendUniqueRecords([one], one, 200).map((item) => item.id), ['one'])
assert.deepEqual(appendUniqueRecords([one, two], three, 200).map((item) => item.id), [
  'one',
  'two',
  'three',
])

console.log('record-merge self-check ok')
