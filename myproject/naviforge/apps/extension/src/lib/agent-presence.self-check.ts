import assert from 'node:assert/strict'

import {
  colorForAgentTask,
  formatAgentGroupTitle,
  isPresenceLive,
  parseAgentPresence,
  PRESENCE_STALE_MS,
} from './agent-presence'

assert.equal(formatAgentGroupTitle('介绍一下这个项目'), 'NaviForge · 介绍一下这个项目')
assert(formatAgentGroupTitle('a'.repeat(80)).startsWith('NaviForge · '))
assert(formatAgentGroupTitle('a'.repeat(80)).endsWith('…'))
assert.equal(colorForAgentTask('task-a'), colorForAgentTask('task-a'))
assert.notEqual(colorForAgentTask('alpha'), colorForAgentTask('omega'))

const live = parseAgentPresence({
  running: true,
  tabId: 7,
  heartbeat: 1_000,
  action: 'dom.click',
})
assert(live?.action === 'dom.click')
assert(isPresenceLive(live, 7, 1_000 + 100))
assert(!isPresenceLive(live, 8, 1_000 + 100), 'other tab is not locked')
assert(!isPresenceLive(live, 7, 1_000 + PRESENCE_STALE_MS + 1), 'stale heartbeat releases lock')
assert(
  !isPresenceLive({ running: true, tabId: 7, heartbeat: 1_000, waiting: true }, 7, 1_100),
  'HITL waiting hides mask'
)
assert.equal(parseAgentPresence({ running: true }), undefined)

console.log('agent-presence self-check ok')
