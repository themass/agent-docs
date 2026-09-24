import assert from 'node:assert/strict'

import type { TraceRecord } from '@naviforge/session'

import { leafProgressLine } from './leaf-feed.js'

const base = {
  schema: 1 as const,
  at: 1,
  runId: 'leaf-1',
  parentRunId: 'parent',
  channel: 'trace' as const,
}

assert.equal(
  leafProgressLine({
    ...base,
    id: 't1',
    type: 'tool.result',
    payload: { tool: 'dom_read', arguments: {}, ok: false, error: { code: 'bad_args', message: 'briefs invalid', recoverable: true } },
  }),
  '子任务 · dom_read 失败: briefs invalid'
)

assert.equal(
  leafProgressLine({
    ...base,
    id: 't2',
    type: 'model.turn',
    payload: { status: 'act', summary: 'read file', call: { tool: 'network_read', arguments: { mode: 'body' } } },
  }),
  '子任务 · network_read'
)

console.log('leaf-feed self-check ok')
