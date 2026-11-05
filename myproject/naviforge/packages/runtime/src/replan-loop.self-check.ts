import assert from 'node:assert/strict'
import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'

import type { AgentOptions } from './agent.js'
import { Agent, AgentCtx } from './agent-ctx.js'
import { ActionLoopHook, DedupeObservationHook } from './builtin-hooks.js'
import { createActionLoopGate, decideActionLoop, recordActionLoopSuccess } from './loop-gates.js'
import { markObservationSeen } from './loop-gate-state.js'

const snap: DomSnapshot = {
  revision: 1,
  url: 'https://example.test/page',
  title: 't',
  header: '',
  content: '',
  footer: '',
}

function testAgent(over: Partial<AgentOptions> = {}): Agent {
  return new Agent({
    task: '介绍这个页面',
    llm: { baseURL: 'http://x', apiKey: 'x', model: 'x' },
    dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
    ...over,
  })
}

{
  const gate = createActionLoopGate(2)
  const key = 'dom_screenshot|https://example.test/page'
  assert.equal(decideActionLoop(gate, key), 'allow')
  recordActionLoopSuccess(gate, key)
  assert.equal(decideActionLoop(gate, key), 'allow')
  recordActionLoopSuccess(gate, key)
  assert.equal(decideActionLoop(gate, key), 'skip')
  assert.equal(decideActionLoop(gate, key), 'replan')
}

{
  const hook = new ActionLoopHook()
  const ctx = new AgentCtx(testAgent({ sameActionLimit: 2 }), snap)
  const key = 'dom_screenshot|https://example.test/page'
  ctx.gates.actionLoop.exec.set(key, 2)
  ctx.gates.actionLoop.skip.set(key, 1)
  ctx.toolCall = { tool: 'dom_screenshot', arguments: {} }
  const decision = hook.beforeTool(ctx)
  assert.equal(decision.kind, 'skip_tool')
  if (decision.kind === 'skip_tool') {
    assert.equal(decision.stop, undefined)
    assert.match(decision.log ?? '', /replan/)
  }
  assert.equal(ctx.runtimeState.progress.replanRequired, true)
}

{
  const hook = new DedupeObservationHook()
  const ctx = new AgentCtx(testAgent({}), snap)
  const obsKey = 'dom_read|https://example.test/page|body'
  markObservationSeen(ctx.gates, obsKey, 'prior evidence body')
  ctx.gates.dupSkipByKey.set(obsKey, 2)
  ctx.toolCall = { tool: 'dom_read', arguments: { mode: 'body' } }
  const decision = hook.beforeTool(ctx)
  assert.equal(decision.kind, 'skip_tool')
  if (decision.kind === 'skip_tool') {
    assert.equal(decision.stop, undefined, 'general dedupe no longer hard-stops the run')
    assert.match(decision.log ?? '', /replan/)
  }
  assert.equal(ctx.runtimeState.progress.replanRequired, true)
}

console.log('replan-loop.self-check ok')
