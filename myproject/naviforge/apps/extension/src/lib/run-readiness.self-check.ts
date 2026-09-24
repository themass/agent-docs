import assert from 'node:assert/strict'

import { blockingReadinessItems, type RunReadinessItem } from './run-readiness.js'

const items: RunReadinessItem[] = [
  { id: 'api_key', ok: true, label: 'key', blocking: true },
  { id: 'tab', ok: false, label: 'tab', detail: 'bad', blocking: true },
  { id: 'dbg', ok: false, label: 'dbg', blocking: false },
]
assert.equal(blockingReadinessItems(items).length, 1)
assert.equal(blockingReadinessItems(items)[0]?.id, 'tab')

console.log('run-readiness self-check ok')
