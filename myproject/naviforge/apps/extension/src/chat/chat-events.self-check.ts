import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import { groupByTurn, partitionChildTraceViews, sessionToChatEvents } from './chat-events'

const records: TraceRecord[] = [
  { schema: 1, id: 'task', at: 1, runId: 'run', taskId: 'task', channel: 'conversation', type: 'user.task', payload: { text: 'summarize' } },
  {
    schema: 1,
    id: 'model',
    at: 2,
    runId: 'run',
    taskId: 'task',
    turn: 0,
    channel: 'trace',
    type: 'model.turn',
    payload: { status: 'act', summary: 'read', call: { tool: 'dom_read', arguments: { mode: 'body' } } },
  },
]
const views = sessionToChatEvents(records)
assert.equal(views.length, 2)
assert.equal(views[1]?.variant, 'step')

const partitioned = partitionChildTraceViews([
  { id: 'a', at: 1, variant: 'task', title: 't', body: 'x' },
  {
    id: 'b',
    at: 2,
    parentRunId: 'parent',
    runId: 'child',
    variant: 'tool',
    title: 'dom_read',
    body: 'ok',
  },
])
assert.equal(partitioned.main.length, 1)
assert.equal(partitioned.childrenByParent.get('parent')?.length, 1)
assert.equal(groupByTurn(views).length, 2)
assert.equal(
  groupByTurn([
    {
      id: 'child-a',
      at: 3,
      runId: 'child-a',
      parentRunId: 'parent',
      taskId: 'task',
      turn: 0,
      variant: 'step',
      title: '计划',
      body: 'first child',
    },
    {
      id: 'child-b',
      at: 4,
      runId: 'child-b',
      parentRunId: 'parent',
      taskId: 'task',
      turn: 0,
      variant: 'step',
      title: '计划',
      body: 'second child',
    },
  ]).length,
  2,
  'concurrent child runs with the same parent and turn stay separate'
)
console.log('chat-events self-check ok')
