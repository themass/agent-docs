import assert from 'node:assert/strict'

import {
  AGENT_CAPABILITY_PRESET_VALUES,
  capabilityPresetPatch,
  inferCapabilityPreset,
} from './agent-capabilities.js'
import { DEFAULT_PRIVACY, type PrivacySettings } from './settings.js'

assert.equal(inferCapabilityPreset(DEFAULT_PRIVACY), 'daily')

const media: PrivacySettings = { ...DEFAULT_PRIVACY, ...capabilityPresetPatch('media') }
assert.equal(inferCapabilityPreset(media), 'media')
assert.equal(media.networkEnabled, true)
assert.equal(media.captureNetworkBodies, true)

assert.equal(AGENT_CAPABILITY_PRESET_VALUES.power.allowDomInject, true)

console.log('agent-capabilities.self-check ok')
