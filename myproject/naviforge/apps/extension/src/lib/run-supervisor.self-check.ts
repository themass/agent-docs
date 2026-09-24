import assert from 'node:assert/strict'

import { isValidBackgroundRunRequest } from './run-supervisor-request.js'

assert.equal(isValidBackgroundRunRequest(null), false)
assert.equal(isValidBackgroundRunRequest({}), false)
assert.equal(
  isValidBackgroundRunRequest({
    id: 'run-1',
    task: 'hello',
    tabId: 1,
    llm: { apiKey: 'k', baseURL: 'https://example.com', model: 'm' },
  }),
  true
)

console.log('run-supervisor self-check ok')
