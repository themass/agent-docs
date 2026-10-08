import assert from 'node:assert/strict';
import { resolveBuiltinToolCall } from './builtin-tool-resolver.js';
assert.deepEqual(resolveBuiltinToolCall('dom_read', { mode: 'body' }), {
    tool: 'dom_read_page',
    arguments: {},
});
assert.deepEqual(resolveBuiltinToolCall('dom_read', { mode: 'list', n: 5 }), {
    tool: 'dom_extract_content',
    arguments: { n: 5 },
});
assert.deepEqual(resolveBuiltinToolCall('workspace', { action: 'read', path: 'a.txt' }), {
    tool: 'workspace_read',
    arguments: { path: 'a.txt' },
});
assert.deepEqual(resolveBuiltinToolCall('workspace', { action: 'glob', pattern: '**/*.md' }), {
    tool: 'workspace_glob',
    arguments: { pattern: '**/*.md' },
});
assert.deepEqual(resolveBuiltinToolCall('network_read', { mode: 'list', limit: 5 }), {
    tool: 'network_list',
    arguments: { limit: 5 },
});
assert.deepEqual(resolveBuiltinToolCall('network_read', { mode: 'media' }), {
    tool: 'network_media_hints',
    arguments: {},
});
assert.deepEqual(resolveBuiltinToolCall('dom_click', { index: 1 }), {
    tool: 'dom_click',
    arguments: { index: 1 },
});
assert.deepEqual(resolveBuiltinToolCall('browser_act', { action: 'click', index: 1, revision: 1 }), {
    tool: 'dom_click',
    arguments: { index: 1, revision: 1 },
});
assert.deepEqual(resolveBuiltinToolCall('browser_observe', { action: 'read', mode: 'list', n: 5 }), {
    tool: 'dom_extract_content',
    arguments: { n: 5 },
});
assert.deepEqual(resolveBuiltinToolCall('tabs', { action: 'open', url: 'https://example.com' }), {
    tool: 'tabs_open',
    arguments: { url: 'https://example.com' },
});
assert.deepEqual(resolveBuiltinToolCall('network', { action: 'read', mode: 'media' }), {
    tool: 'network_media_hints',
    arguments: {},
});
assert.deepEqual(resolveBuiltinToolCall('workspace', { action: 'script_save', filename: 'a.py', content: 'x' }), {
    tool: 'script_save',
    arguments: { filename: 'a.py', content: 'x' },
});
console.log('builtin-tool-resolver self-check ok');
