import assert from 'node:assert/strict'

import type { TraceRecord } from '@naviforge/session'

import { clipLiveLine, headerStatusDetail, latestReasoning, pushLiveFeed } from './live-thinking'

assert.equal(clipLiveLine('  hello   world  '), 'hello world')
assert.equal(clipLiveLine('x'.repeat(200), 10).endsWith('…'), true)

let feed = pushLiveFeed([], '正在执行 dom_read')
assert.deepEqual(feed, ['正在执行 dom_read'])
feed = pushLiveFeed(feed, '正在执行 dom_read')
assert.equal(feed.length, 1)
feed = pushLiveFeed(feed, '已完成 dom_read')
assert.equal(feed.length, 2)

const records = [
  {
    schema: 1,
    id: '1',
    at: 1,
    runId: 'run',
    channel: 'trace',
    type: 'model.turn',
    payload: {
      status: 'think',
      summary: 'plan',
      io: { user: 'task', reasoning: '  compare repos\nstep two ', assistant: '' },
    },
  },
] as TraceRecord[]
assert.ok(latestReasoning(records)?.includes('compare repos'))
assert.ok(headerStatusDetail(true, '已完成：dom_navigate') === '继续执行…')
assert.equal(headerStatusDetail(false, '已完成：dom_navigate'), '已完成：dom_navigate')

console.log('live-thinking.self-check ok')
