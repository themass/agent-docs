import assert from 'node:assert/strict'

import { hasResumeRequest } from './settings'

assert.equal(hasResumeRequest({ threadId: 'thread-1', page: { tabId: 7 } }), false)
assert.equal(hasResumeRequest({ sessionId: 'session-1' }), true)
assert.equal(hasResumeRequest({ task: 'continue this task' }), true)
