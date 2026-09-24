import assert from 'node:assert/strict'

import { cleanQueuedTasks } from './agent-run-controller.js'

assert.deepEqual(cleanQueuedTasks([{ id: 'task-1', text: '  follow up  ' }]), [
  { id: 'task-1', text: 'follow up' },
])
assert.deepEqual(cleanQueuedTasks([{ id: '', text: 'discard' }]), [])

console.log('agent-run-controller self-check ok')
