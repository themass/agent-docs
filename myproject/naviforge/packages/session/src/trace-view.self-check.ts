import assert from 'node:assert/strict'
import { createTraceRecord } from './trace.js'
import { projectTraceView } from './trace-view.js'

const view = projectTraceView(
  createTraceRecord({
    type: 'run.result',
    runId: 'r1',
    payload: { text: 'done' },
  })
)
assert.equal(view?.variant, 'result')
assert.equal(view?.body, 'done')

const hidden = projectTraceView(
  createTraceRecord({
    type: 'run.context',
    runId: 'r1',
    payload: { systemPrompt: 'secret kernel', tools: ['dom_read'] },
  })
)
assert.equal(hidden, null)

const tools = projectTraceView(
  createTraceRecord({
    type: 'run.tools',
    runId: 'r1',
    payload: {
      catalog: [
        { name: 'dom_click', description: 'Click an element', source: 'builtin' },
        { name: 'mcp__docs__search', description: 'Search docs', source: 'mcp' },
      ],
    },
  })
)
assert.equal(tools?.variant, 'tools')
assert.equal(tools?.toolCatalog?.length, 2)

const clarify = projectTraceView(
  createTraceRecord({
    type: 'intake.question',
    runId: 'r1',
    payload: {
      round: 0,
      questions: [{ id: 'skill', prompt: '你说的 Skill 具体指什么？', kind: 'text' }],
    },
  })
)
assert.equal(clarify?.variant, 'question')
assert.match(clarify?.body ?? '', /Skill/)

console.log('trace-view self-check ok')
