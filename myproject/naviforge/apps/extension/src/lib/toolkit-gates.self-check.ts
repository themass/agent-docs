import assert from 'node:assert/strict'

import { toolkitGateBlocked, toolkitGatesFromPrivacy } from './toolkit-gates.js'

const open = toolkitGatesFromPrivacy({ visionEnabled: true, networkEnabled: true })
assert.equal(toolkitGateBlocked(open, 'visionEnabled'), null, 'vision on allows ocr')
assert.equal(toolkitGateBlocked(open, 'networkEnabled'), null, 'network on allows ip lookup')

const closed = toolkitGatesFromPrivacy({ visionEnabled: false, networkEnabled: false })
assert.ok(toolkitGateBlocked(closed, 'visionEnabled')?.includes('视觉'), 'vision off blocks agent vision')
assert.ok(toolkitGateBlocked(closed, 'networkEnabled')?.includes('网络'), 'network off blocks ip')

console.log('toolkit-gates self-check ok')
