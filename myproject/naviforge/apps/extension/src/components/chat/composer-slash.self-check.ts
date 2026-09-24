import assert from 'node:assert/strict'

import {
  buildSlashCommandRegistry,
  filterSlashCommands,
  parseSlashDraftWithRegistry,
  resolveSlashCommand,
} from './composer-slash-registry.ts'

const registry = buildSlashCommandRegistry([])

assert.deepEqual(
  filterSlashCommands('hel', registry).map((item) => item.name),
  ['hello']
)
assert.deepEqual(
  filterSlashCommands('lo', registry).map((item) => item.name),
  ['hello']
)
assert.deepEqual(
  filterSlashCommands('sum', registry).map((item) => item.name),
  ['summarize']
)
assert.ok(filterSlashCommands('', registry).length >= 6)
assert.equal(resolveSlashCommand('status', registry)?.name, 'check')
assert.equal(parseSlashDraftWithRegistry('/hello world', null, registry).kind, 'locked')
assert.equal(parseSlashDraftWithRegistry('/', null, registry).kind, 'menu')
assert.equal(parseSlashDraftWithRegistry('/hel', null, registry).kind, 'menu')
assert.equal(parseSlashDraftWithRegistry('/hello', null, registry).kind, 'menu')

console.log('composer slash self-check ok')
