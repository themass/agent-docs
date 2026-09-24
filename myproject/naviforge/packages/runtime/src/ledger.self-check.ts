import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import { RunLedger } from './ledger.js'

const record = (id: string, type: TraceRecord['type'], payload: TraceRecord['payload']): TraceRecord =>
  ({
    schema: 1,
    id,
    at: Number(id.replace(/\D/g, '')) || 1,
    runId: 'run-1',
    channel: type === 'user.steer' ? 'conversation' : 'trace',
    type,
    payload,
  }) as TraceRecord

const ledger = new RunLedger()
ledger.append(record('steer-1', 'user.steer', { texts: ['stay'], phase: 'pre_model' }))
for (let i = 0; i < 12; i += 1) {
  ledger.append(
    record(`tool-${i}`, 'tool.result', {
      tool: 'dom_click',
      arguments: { index: i },
      ok: true,
      data: { trace: 'y'.repeat(800) },
    })
  )
}

const before = ledger.all().length
assert.equal(before, 13, 'append-only ledger keeps every record')
assert.ok(
  ledger.all().some((entry) => entry.type === 'user.steer'),
  'full log keeps steer'
)

ledger.append(record('note-1', 'run.note', { text: 'USER ANSWER: 确认上传', topic: 'internal' }))
assert.ok(
  ledger.all().some((entry) => entry.type === 'run.note' && entry.payload.text.includes('确认上传')),
  'run.note audit lines are preserved'
)

const approval = new RunLedger()
approval.append(record('tool-1', 'tool.result', { tool: 'dom_click', arguments: {}, ok: true }))
approval.append(record('ask-1', 'run.ask', { question: '确认上传？', wait: 'user' }))
approval.append(record('tool-2', 'tool.result', { tool: 'dom_upload', arguments: {}, ok: true }))
assert.ok(
  approval.all().some((entry) => entry.type === 'run.ask'),
  'HITL facts remain records'
)

console.log('ledger.self-check ok')
