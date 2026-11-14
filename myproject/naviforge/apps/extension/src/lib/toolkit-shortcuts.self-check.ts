import assert from 'node:assert/strict'

import {
  manifestCommands,
  manifestSuggestedShortcutRows,
  shortcutDisplayForCatalog,
  TOOLKIT_SHORTCUT_ROWS,
} from './toolkit-shortcuts.js'

assert.ok(TOOLKIT_SHORTCUT_ROWS.length >= 5, 'shortcut table populated')
assert.ok(manifestSuggestedShortcutRows().length <= 4, 'Chrome manifest suggested_key cap')
assert.equal(manifestSuggestedShortcutRows().length, 4, 'four defaults: ⌥⇧N ⌥⇧A ⌥⇧S ⌘⇧S')
assert.equal(shortcutDisplayForCatalog('fullpage'), '⌥⇧S')
assert.equal(shortcutDisplayForCatalog('translate'), '⌥⇧T')
assert.equal(shortcutDisplayForCatalog('json'), undefined)

const commands = manifestCommands()
assert.ok(commands['nf-capture-full']?.suggested_key?.mac === 'Alt+Shift+S')
assert.ok(!commands['nf-translate']?.suggested_key, 'translate is user-bound')

console.log('toolkit-shortcuts self-check ok')
