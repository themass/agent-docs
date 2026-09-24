import assert from 'node:assert/strict'
import { createMemorySessionManager, AgentSession, createTraceRecord } from '@naviforge/session'

import { createLiveSessionBridge } from './live-session.js'

const store = createMemorySessionManager()
const thread = await store.createThread('live')
const session = await store.createSession({ task: 'hello', threadId: thread.id })
let records: readonly import('@naviforge/session').TraceRecord[] = []
const bridge = createLiveSessionBridge({
  getSessionId: () => session.id,
  getRunId: () => 'bg-run',
  manager: store,
  onRecords: (next) => {
    records = next
  },
})

await bridge.bindSession(session.id)
bridge.appendLocal('run.log', { message: 'local notice' })
assert.equal(records.length, 1, 'appendLocal updates subscribed records')
assert.equal(records[0]?.runId, 'bg-run', 'appendLocal uses active run id')

const remote = createTraceRecord({
  type: 'run.result',
  runId: 'bg-run',
  payload: { text: 'done' },
})
bridge.ingest(remote)
assert.equal(records.length, 2, 'ingest appends without duplicate persist path')
bridge.ingest(remote)
assert.equal(records.length, 2, 'duplicate ingest is ignored')

bridge.dispose()
console.log('live-session self-check ok')
