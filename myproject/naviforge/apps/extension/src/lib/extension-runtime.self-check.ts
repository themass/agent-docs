import assert from 'node:assert/strict'

import {
  extensionRuntimeAlive,
  isExtensionContextInvalidated,
  runIfExtensionAlive,
} from './extension-runtime.js'

assert.equal(isExtensionContextInvalidated(new Error('Extension context invalidated.')), true)
assert.equal(isExtensionContextInvalidated(new Error('other')), false)
assert.equal(typeof extensionRuntimeAlive(), 'boolean')

let ran = false
runIfExtensionAlive(() => {
  ran = true
})
assert.equal(ran, extensionRuntimeAlive())

console.log('extension-runtime self-check ok')
