import assert from 'node:assert/strict'

import { pageAtBottom, pickLargestScrollable } from './scroll-page.js'

assert.equal(pageAtBottom(100, 800, 900), true, 'near bottom counts as bottom')
assert.equal(pageAtBottom(0, 800, 5000), false, 'top is not bottom')

const idx = pickLargestScrollable([
  { scrollHeight: 100, clientHeight: 100, clientWidth: 400, overflowY: 'auto' },
  { scrollHeight: 4000, clientHeight: 800, clientWidth: 900, overflowY: 'scroll' },
  { scrollHeight: 2000, clientHeight: 600, clientWidth: 300, overflowY: 'auto' },
])
assert.equal(idx, 1, 'largest scrollable area wins')

console.log('scroll-page self-check ok')
