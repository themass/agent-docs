import assert from 'node:assert/strict'

import { resolveBuiltinToolCall } from './builtin-tool-resolver.js'

assert.deepEqual(resolveBuiltinToolCall('dom_read', { mode: 'body' }), {
  tool: 'dom_read_page',
  arguments: {},
})
assert.deepEqual(resolveBuiltinToolCall('dom_read', { mode: 'list', n: 5 }), {
  tool: 'dom_extract_content',
  arguments: { n: 5 },
})
assert.deepEqual(resolveBuiltinToolCall('workspace', { action: 'read', path: 'a.txt' }), {
  tool: 'workspace_read',
  arguments: { path: 'a.txt' },
})
assert.deepEqual(resolveBuiltinToolCall('workspace', { action: 'glob', pattern: '**/*.md' }), {
  tool: 'workspace_glob',
  arguments: { pattern: '**/*.md' },
})
assert.deepEqual(resolveBuiltinToolCall('network_read', { mode: 'list', limit: 5 }), {
  tool: 'network_list',
  arguments: { limit: 5 },
})
assert.deepEqual(resolveBuiltinToolCall('network_read', { mode: 'media' }), {
  tool: 'network_media_hints',
  arguments: {},
})
assert.deepEqual(resolveBuiltinToolCall('dom_click', { index: 1 }), {
  tool: 'dom_click',
  arguments: { index: 1 },
})

console.log('builtin-tool-resolver self-check ok')
