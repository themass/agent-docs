import assert from 'node:assert/strict'

import { createTraceRecord } from '@naviforge/session'

import {
  createLlmContextCompactor,
  serializeRecordsForCompaction,
} from './context-compaction.js'

// parseCompactionJson is internal — covered by compactor integration below.

const records = [
  createTraceRecord({
    type: 'user.task',
    payload: { text: 'compare two repos' },
    runId: 'r1',
  }),
  createTraceRecord({
    type: 'tool.result',
    payload: {
      tool: 'dom_read',
      arguments: { mode: 'body' },
      ok: true,
      data: { text: 'page body excerpt' },
    },
    runId: 'r1',
  }),
]

assert.ok(serializeRecordsForCompaction(records).includes('compare two repos'))

let sentBody: string | undefined
const prevFetch = globalThis.fetch
globalThis.fetch = (async (_url, init) => {
  sentBody = String(init?.body ?? '')
  return new Response(
    JSON.stringify({
      choices: [
        {
          message: {
            content: JSON.stringify({
              summary: 'User asked to compare repos; read page once.',
              preserved_constraints: ['CONSTRAINT: stay on task'],
              open_work: [],
            }),
          },
        },
      ],
      usage: { total_tokens: 42 },
    }),
    { status: 200, headers: { 'Content-Type': 'application/json' } }
  )
}) as typeof fetch

try {
  const compactor = createLlmContextCompactor({
    llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
  })
  const result = await compactor.compact({
    records,
    constraints: ['CONSTRAINT: stay on task'],
    openWork: [],
  })
  assert.equal(result.mode, 'llm')
  assert.ok(result.summary.includes('compare'))
  assert.equal(result.tokenUsage, 42)
  assert.ok(!('tools' in JSON.parse(sentBody ?? '{}')), 'compaction call omits tools[]')
} finally {
  globalThis.fetch = prevFetch
}

console.log('context-compaction self-check ok')
