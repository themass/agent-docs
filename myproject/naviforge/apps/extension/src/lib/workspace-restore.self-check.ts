import assert from 'node:assert/strict'

import { canRestoreTabWorkspace } from './tab-workspace'

const stable = {
  generation: 4,
  currentGeneration: 4,
  running: false,
  resumeLocked: false,
  hasResumeRequest: false,
}

assert.equal(canRestoreTabWorkspace(stable), true)
assert.equal(canRestoreTabWorkspace({ ...stable, currentGeneration: 5 }), false)
assert.equal(canRestoreTabWorkspace({ ...stable, running: true }), false)
assert.equal(canRestoreTabWorkspace({ ...stable, resumeLocked: true }), false)
assert.equal(canRestoreTabWorkspace({ ...stable, hasResumeRequest: true }), false)
