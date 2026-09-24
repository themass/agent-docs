import assert from 'node:assert/strict'

import { formatRunElapsed, formatRunSubtitle } from './toolkit-run-result'

assert.equal(formatRunElapsed(480), '480 ms')
assert.equal(formatRunElapsed(1500), '1.5 s')
assert.equal(formatRunSubtitle({ target: 'example.com', elapsedMs: 200 }), 'example.com · 200 ms')
assert.equal(formatRunSubtitle({ elapsedMs: 1000 }), '1.0 s')

console.log('toolkit-run-result self-check ok')
