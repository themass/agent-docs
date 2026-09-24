import assert from 'node:assert/strict'

import { formatBytes } from './format-bytes'

assert.equal(formatBytes(0), '0 B')
assert.equal(formatBytes(1024), '1 KB')
assert.equal(formatBytes(1536), '1.5 KB')
assert.equal(formatBytes(null), '—')

console.log('format-bytes self-check ok')
