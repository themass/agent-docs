import assert from 'node:assert/strict'

import { CONTEXT_MENU, isContextMenuAction } from './context-menu.js'

assert.equal(isContextMenuAction(CONTEXT_MENU.openAgent), true)
assert.equal(isContextMenuAction(CONTEXT_MENU.askSelection), true)
assert.equal(isContextMenuAction('unknown'), false)
assert.equal(isContextMenuAction(42), false)

console.log('context-menu self-check ok')
