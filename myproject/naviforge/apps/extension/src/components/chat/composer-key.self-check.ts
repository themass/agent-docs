import assert from 'node:assert/strict'

import { composerEnterIntent, composerIsCompact, shouldSubmitComposer } from './composer-key'

const base = { key: 'Enter' as const, shiftKey: false, altKey: false, ctrlKey: false, isComposing: false, keyCode: 13 }

assert(!shouldSubmitComposer({ ...base, isComposing: true }), 'IME candidate confirmation never submits')
assert(!shouldSubmitComposer({ ...base, keyCode: 229 }), 'IME fallback key code never submits')
assert(!shouldSubmitComposer({ ...base, shiftKey: true }), 'Shift+Enter inserts a newline')
assert.equal(composerEnterIntent({ ...base, shiftKey: true }), null, 'Shift+Enter is newline')
assert.equal(composerEnterIntent(base), 'send', 'Enter sends')
assert(shouldSubmitComposer(base), 'plain Enter submits')
assert.equal(
  composerEnterIntent({ ...base, altKey: true }),
  'send',
  'Alt+Enter still sends'
)
assert.equal(
  composerEnterIntent({ ...base, ctrlKey: true }),
  'steer',
  'Ctrl+Enter is 纠偏'
)
assert(
  shouldSubmitComposer({ ...base, altKey: true }),
  'Alt+Enter still submits'
)

const idle = { focused: false, value: '', hasAttachment: false, listening: false }
assert(composerIsCompact(idle), 'empty idle is compact')
assert(!composerIsCompact({ ...idle, focused: true }), 'focus expands')
assert(!composerIsCompact({ ...idle, value: 'hi' }), 'text expands')
assert(!composerIsCompact({ ...idle, hasAttachment: true }), 'attachment expands')
assert(!composerIsCompact({ ...idle, listening: true }), 'mic expands')

console.log('composer key self-check ok')
