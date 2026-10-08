import assert from 'node:assert/strict';
import { formatExtractContentTrace, formatExtractDomTrace, formatReadPageTrace, formatToolTrace, } from './format-tool-trace.js';
assert.ok(formatReadPageTrace({ text: 'hello', source: 'article' }).includes('dom_read body ok'));
assert.ok(formatExtractDomTrace({ items: [{ index: 1, href: 'https://x', title: 't' }] }).includes('dom_extract_dom'));
assert.ok(formatExtractContentTrace({ items: [{ title: 'a', url: 'https://a' }] }).includes('dom_read list'));
assert.equal(formatToolTrace('dom_read', { text: 'x' }, { mode: 'body' }), formatReadPageTrace({ text: 'x' }));
assert.equal(formatToolTrace('dom_read', { items: [] }, { mode: 'list' }), formatExtractContentTrace({ items: [] }));
assert.ok(formatToolTrace('workspace_read', { path: 'a.txt' }).includes('path=a.txt'));
console.log('format-tool-trace self-check ok');
