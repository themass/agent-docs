import assert from 'node:assert/strict'

import { parseFrameHops } from './dom-frame-supplement.js'

assert.deepEqual(parseFrameHops(undefined), [])
assert.deepEqual(parseFrameHops(''), [])
assert.deepEqual(parseFrameHops('f0'), [{ token: 'f0', index: 0 }])
assert.deepEqual(parseFrameHops('f0>>f1'), [
  { token: 'f0', index: 0 },
  { token: 'f1', index: 1 },
])
assert.deepEqual(parseFrameHops('F2>>f0>>f3'), [
  { token: 'f2', index: 2 },
  { token: 'f0', index: 0 },
  { token: 'f3', index: 3 },
])
assert.equal(parseFrameHops('0'), null)
assert.equal(parseFrameHops('f0>f1'), null)
assert.equal(parseFrameHops('main>>f0'), null)
assert.equal(parseFrameHops('f0>>x1'), null)

console.log('dom-frame-supplement.self-check ok')
