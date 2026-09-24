// @ts-nocheck
import assert from 'node:assert/strict'

import { readTabWorkspace, writeTabWorkspace } from './tab-workspace'

const workspace = (task: string) => ({
  task,
  activeThreadId: 'thread-1',
  traceOpen: true,
  targetTab: null,
})
const first = writeTabWorkspace({}, 7, workspace('first question'))
const second = writeTabWorkspace(first, 9, workspace('second question'))

assert.deepEqual(readTabWorkspace(second, 7), workspace('first question'))
assert.deepEqual(readTabWorkspace(second, 9), workspace('second question'))

console.log('tab-workspace self-check ok')
