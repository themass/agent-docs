import assert from 'node:assert/strict'

import {
  buildSlashCommandRegistry,
  filterSlashCommands,
  parseSlashDraftWithRegistry,
  resolveSlashCommand,
} from './composer-slash-registry.ts'

const registry = buildSlashCommandRegistry([
  {
    manifest: { id: 'demo-skill', version: '1', description: 'Demo' },
    instructions: 'body',
  },
])

assert.deepEqual(
  filterSlashCommands('hel', registry).map((item) => item.name),
  ['hello']
)
assert.ok(filterSlashCommands('skill:demo', registry).some((item) => item.name === 'skill:demo-skill'))
assert.equal(resolveSlashCommand('status', registry)?.name, 'check')
assert.equal(parseSlashDraftWithRegistry('/skill:demo-skill run', null, registry).kind, 'locked')
assert.equal(registry.find((item) => item.skillId === 'demo-skill')?.name, 'skill:demo-skill')

console.log('composer slash registry self-check ok')
