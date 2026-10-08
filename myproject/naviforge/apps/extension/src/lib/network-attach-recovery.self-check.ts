import assert from 'node:assert/strict'

import { classifyNetworkAttachCause } from './network-recorder.js'

assert.equal(classifyNetworkAttachCause('Another debugger is already attached'), 'devtools_open')
assert.equal(classifyNetworkAttachCause('Another extension has debugger'), 'foreign_debugger')
assert.equal(classifyNetworkAttachCause(''), 'unknown')

console.log('network-attach-recovery.self-check ok')
