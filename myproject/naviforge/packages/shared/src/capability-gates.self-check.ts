import assert from 'node:assert/strict'

import {
  applyAgentCapabilityGates,
  capabilityGatesFromPrivacy,
  DEFAULT_AGENT_CAPABILITY_GATES,
} from './capability-gates.js'

assert.deepEqual(
  applyAgentCapabilityGates(DEFAULT_AGENT_CAPABILITY_GATES, {
    networkEnabled: false,
    allowNetworkIntercept: true,
  }),
  { ...DEFAULT_AGENT_CAPABILITY_GATES, networkEnabled: false, allowNetworkIntercept: false }
)

assert.deepEqual(
  capabilityGatesFromPrivacy({ networkEnabled: false, allowNetworkIntercept: true }),
  { ...DEFAULT_AGENT_CAPABILITY_GATES, networkEnabled: false, allowNetworkIntercept: false }
)

console.log('capability-gates self-check ok')
