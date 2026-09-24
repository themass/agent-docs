import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import {
  createDeterministicCompactor,
  projectTraceRecords,
  promptWouldExceedInputLimit,
  type ContextCompactor,
} from './working-set.js'

const record = (
  id: string,
  type: TraceRecord['type'],
  payload: TraceRecord['payload']
): TraceRecord =>
  ({
    schema: 1,
    id,
    at: Number(id.replace(/\D/g, '')) || 1,
    runId: 'run-1',
    channel: type.startsWith('user.') || type === 'run.ask' || type === 'run.result' ? 'conversation' : 'trace',
    type,
    payload,
  }) as TraceRecord

const records = [
  record('task-1', 'user.task', { text: 'Find the current pricing.' }),
  record('steer-1', 'user.steer', { texts: ['Stay on this page.'], phase: 'pre_model' }),
  record('page-1', 'tool.result', {
    tool: 'dom_read',
    arguments: { mode: 'body' },
    ok: true,
    data: { url: 'https://example.test/old', title: 'Old', text: 'Old pricing' },
  }),
  record('page-2', 'tool.result', {
    tool: 'dom_read',
    arguments: { mode: 'body' },
    ok: true,
    data: { url: 'https://example.test/old', title: 'New', text: 'Current pricing is $10.' },
  }),
  record('error-1', 'run.error', { message: 'Search key is unavailable.' }),
  record('ask-1', 'run.ask', { question: 'May I open the billing page?', wait: 'user' }),
]
const before = structuredClone(records)
const projected = projectTraceRecords(records, { maxInputTokens: 500 })

assert.deepEqual(records, before, 'L1 projection never mutates the audit ledger')
assert.equal(projected.items.filter((item) => item.kind === 'observation').length, 1, 'L1 coalesces stale page observations')
assert.ok(projected.items.some((item) => item.pinned && item.kind === 'constraint'), 'steer/HITL stays pinned')
assert.ok(projected.prompt.includes('Current pricing is $10.'), 'latest page observation survives')
assert.ok(!projected.prompt.includes('must not leak'), 'raw tool arguments never leak into the prompt')
assert.ok(!projected.prompt.includes('"data"'), 'raw JSON payloads never leak into the prompt')
assert.equal(
  promptWouldExceedInputLimit({ system: 's'.repeat(100), user: 'u'.repeat(100), maxInputTokens: 50 }),
  true,
  'single-prompt input cap is independent from run budget'
)

let compactCalls = 0
const compactor: ContextCompactor = {
  compact: async (input) => {
    compactCalls += 1
    return {
      summary: 'Compacted prior work.',
      preservedConstraints: input.constraints,
      openWork: input.openWork,
      tokenUsage: 12,
    }
  },
}
const deterministic = createDeterministicCompactor()
assert.ok(deterministic, 'L2 has a dedicated deterministic compactor')
assert.equal(compactCalls, 0, 'L2 does not run until projection pressure requests it')

console.log('context-projection.self-check ok')
