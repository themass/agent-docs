import assert from 'node:assert/strict'

import type { RecordedDomAction } from '@naviforge/playbook'

import { recipeStepsFromRecordedActions } from './recipe-from-run.js'

const actions: RecordedDomAction[] = [
  { tool: 'dom_click', index: 3, selector: '#download', network: { id: 'n1', method: 'GET', url: 'https://cdn.example/a.m3u8', ts: 0 } },
]

const steps = recipeStepsFromRecordedActions(actions, 'media_extract')
assert.ok(steps.some((step) => step.use === 'page_signals_playback'))
assert.ok(steps.some((step) => step.use === 'network_wait' && step.urlIncludes === '.m3u8'))

console.log('recipe-from-run self-check ok')
