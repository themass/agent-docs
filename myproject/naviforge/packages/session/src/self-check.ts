import assert from 'node:assert/strict'

import { AgentSession } from './agent-session.js'
import {
  isContinuationMessage,
  sessionDisplayTitle,
} from './continuation.js'
import { appendRecordForTest, createMemorySessionManager } from './memory-session-manager.js'
import { buildThreadContext } from './thread-context.js'
import { memoryPatchFromRun, mergeThreadMemory } from './thread-memory.js'
import type { SessionAuditExport, TraceRecord } from './types.js'
import { createTraceRecord, formatAuditJsonl, validateTraceRecord } from './trace.js'

const sample: SessionAuditExport = { schemaVersion: 1, exportedAt: 1, threads: [], sessions: [] }
assert.equal(sample.schemaVersion, 1, 'schema')

const task: TraceRecord = {
  schema: 1,
  id: 'task-1',
  at: 1,
  runId: 'run-1',
  taskId: 'task-1',
  channel: 'conversation',
  type: 'user.task',
  payload: { text: '介绍 MuseTalk' },
}
assert.deepEqual(validateTraceRecord(task), task, 'canonical records validate unchanged')
const generated = [
  createTraceRecord({
    type: 'run.mode',
    runId: 'run-1',
    payload: { mode: 'model', detail: 'planning' },
  }),
  createTraceRecord({
    type: 'tool.result',
    runId: 'run-1',
    taskId: 'task-1',
    turn: 2,
    payload: { tool: 'dom_click', arguments: { index: 1 }, ok: true, data: { clicked: true } },
  }),
  createTraceRecord({
    type: 'run.ask',
    runId: 'run-1',
    payload: { question: 'Complete the CAPTCHA', wait: 'captcha' },
  }),
  createTraceRecord({
    type: 'run.error',
    runId: 'run-1',
    payload: { message: 'navigation blocked', code: 'scope_violation', tool: 'dom_click' },
  }),
]
for (const record of generated) {
  assert.equal(validateTraceRecord(record).runId, 'run-1', `${record.type} factory record validates`)
}
assert.throws(
  () => validateTraceRecord({ ...task, channel: 'trace' }),
  /channel/,
  'channel must agree with the canonical type'
)

const jsonl = formatAuditJsonl([task])
assert.ok(jsonl.includes('"type":"user.task"'))
assert.match(jsonl, /^\{"schema":1,"id":"task-1","at":1/)
assert.throws(
  () => validateTraceRecord({ record: 'event', ...task }),
  /unexpected field/,
  'legacy JSONL envelopes are rejected instead of translated'
)

const store = createMemorySessionManager()
const thread = await store.createThread('demo')
const session = await AgentSession.create(store, { task: 'hello', threadId: thread.id }, 'run-a')
let events = 0
const unsub = session.subscribe((event) => {
  if (event.type === 'record') events += 1
})
await session.append(
  createTraceRecord({
    type: 'user.task',
    runId: 'run-a',
    payload: { text: 'hello' },
  })
)
await session.append(
  createTraceRecord({
    type: 'run.result',
    runId: 'run-a',
    payload: { text: 'done' },
  })
)
unsub()
assert.equal(events, 2, 'session emits one event per append')
assert.equal(session.records.length, 2, 'session tracks appended records')

const duplicate = createTraceRecord({
  type: 'run.log',
  runId: 'run-a',
  payload: { message: 'dup' },
})
await session.append(duplicate)
await session.append(duplicate)
assert.equal(session.records.length, 3, 'append skips duplicate ids')

const remote = createTraceRecord({
  type: 'run.log',
  runId: 'bg',
  payload: { message: 'remote' },
})
session.ingest(remote)
assert.equal(session.records.length, 4, 'ingest adds remote record')
session.ingest(remote)
assert.equal(session.records.length, 4, 'ingest skips duplicate ids')

const ctx = buildThreadContext(
  {
    ...thread,
    memory: mergeThreadMemory(thread.memory, memoryPatchFromRun({ task: 't', result: 'ok' })),
  },
  await store.listThreadRecords(thread.id)
)
assert.ok(ctx.memory.includes('GOAL'), 'thread context uses slot memory')
assert.ok(ctx.conversation.includes('hello'), 'thread context includes dialogue')

assert.equal(isContinuationMessage('继续'), true)
assert.equal(isContinuationMessage('Continue.'), true)
assert.equal(isContinuationMessage('分析 github'), false)
const originalTask = 'https://github.com/foo 整理 8 月项目'
assert.equal(
  sessionDisplayTitle('继续', [{ ...task, payload: { text: originalTask } }]),
  originalTask
)

const ctx2 = buildThreadContext(
  { ...thread, memory: mergeThreadMemory(thread.memory, memoryPatchFromRun({ task: originalTask, result: 'timeout' })) },
  [
    { ...task, payload: { text: originalTask } },
    { ...generated[3]!, type: 'run.error', payload: { message: 'Run hit the 8-minute wall-clock limit and stopped.' } },
    { ...task, id: 'task-2', payload: { text: '继续' } },
  ]
)
assert.ok(ctx2.conversation.includes('user: https://github.com/foo'), 'thread dialogue is human-readable')
assert.ok(ctx2.conversation.includes('error: Run hit'), 'thread dialogue includes prior failure')
assert.ok(ctx2.conversation.includes('user: 继续'), 'thread dialogue keeps latest user input')

const session2 = await store.createSession({ task: originalTask, threadId: thread.id })
await store.continueSession(session2.id, '继续')
const resumed = await store.getSession(session2.id)
assert.equal(resumed?.task, originalTask, 'continueSession preserves session title')

console.log('session self-check ok')
