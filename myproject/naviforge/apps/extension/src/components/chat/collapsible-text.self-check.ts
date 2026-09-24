import assert from 'node:assert/strict'

import { collapsedPreview, shouldCollapseText, DEFAULT_COLLAPSE_CHARS } from './collapsible-text.js'

const long = 'a'.repeat(DEFAULT_COLLAPSE_CHARS + 10)
assert.equal(shouldCollapseText(long), true)
assert.equal(shouldCollapseText('short'), false)
assert.equal(collapsedPreview(long, DEFAULT_COLLAPSE_CHARS, false).length, DEFAULT_COLLAPSE_CHARS + 1)
assert.equal(collapsedPreview(long, DEFAULT_COLLAPSE_CHARS, true), long)

console.log('collapsible-text self-check ok')
