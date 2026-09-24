import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import { recordView } from './agent-event-projection'

import { setActiveLocale } from '../i18n/t'

const record: TraceRecord = {
  schema: 1,
  id: 'tool-1',
  at: 1,
  runId: 'run-1',
  channel: 'trace',
  type: 'tool.result',
  payload: { tool: 'dom_click', arguments: { index: 1 }, ok: true, data: { clicked: true } },
}
const view = recordView(record)
assert.equal(view?.variant, 'tool')
assert.equal(view?.title, 'dom_click')
assert.equal(view?.request?.includes('index'), true)

setActiveLocale('en')
const taskRecord: TraceRecord = {
  schema: 1,
  id: 'task-1',
  at: 0,
  runId: 'run-1',
  channel: 'conversation',
  type: 'user.task',
  payload: { text: 'hello' },
}
assert.equal(recordView(taskRecord)?.title, 'Task')
setActiveLocale('zh-CN')
assert.equal(recordView(taskRecord)?.title, '任务')

const contextRecord: TraceRecord = {
  schema: 1,
  id: 'ctx-1',
  at: 0,
  runId: 'run-1',
  channel: 'trace',
  type: 'run.context',
  payload: { systemPrompt: 'sys', tools: ['dom_read'] },
}
const ctxView = recordView(contextRecord, 'en')
assert.equal(ctxView, null)

console.log('agent-event-projection self-check ok')
