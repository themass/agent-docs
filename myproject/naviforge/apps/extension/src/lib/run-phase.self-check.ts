import assert from 'node:assert/strict'

import { RUN_STATUS, isWorkspaceActive, isWorkspaceRunning, toSessionRunPhase } from './run-phase.js'

assert.equal(toSessionRunPhase(RUN_STATUS.IDLE), 'idle')
assert.equal(toSessionRunPhase(RUN_STATUS.PREPARING), 'preflight')
assert.equal(toSessionRunPhase(RUN_STATUS.PLANNING), 'running')
assert.equal(toSessionRunPhase(RUN_STATUS.WAITING_USER), 'waiting_user')
assert.equal(toSessionRunPhase(RUN_STATUS.COMPLETED), 'succeeded')
assert.equal(isWorkspaceRunning(RUN_STATUS.ACTING), true)
assert.equal(isWorkspaceActive(RUN_STATUS.PAUSED), true)
assert.equal(toSessionRunPhase(RUN_STATUS.CLARIFYING), 'waiting_user')
assert.equal(isWorkspaceActive(RUN_STATUS.CLARIFYING), true)

console.log('run-phase self-check ok')
