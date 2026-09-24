import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import { capSessionRecords, sortSessionsByRecent, type AgentSession } from './session-model'

const task = (id: string): TraceRecord => ({
  schema: 1, id, at: 1, runId: 'run-1', channel: 'conversation', type: 'user.task', payload: { text: id },
})
const session = (id: string, updatedAt: number): AgentSession => ({
  id, task: id, status: 'success', createdAt: 1, updatedAt, records: [task(id)],
})
assert.equal(sortSessionsByRecent([session('old', 1), session('new', 2)])[0]?.id, 'new')
assert.equal(capSessionRecords(Array.from({ length: 10 }, (_, index) => ({ schema: 1, id: String(index), at: 1, runId: 'run', channel: 'trace', type: 'run.log', payload: { message: String(index) } } as TraceRecord)), 3).length, 3)
console.log('session-model self-check ok')
