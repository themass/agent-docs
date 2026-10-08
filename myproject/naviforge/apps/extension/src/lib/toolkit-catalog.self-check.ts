import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { TOOLKIT_CATALOG } from './toolkit-catalog.js'

const root = dirname(fileURLToPath(import.meta.url))

assert.ok(TOOLKIT_CATALOG.some((item) => item.id === 'page-toollist'), 'catalog includes page tool list')
assert.ok(TOOLKIT_CATALOG.some((item) => item.id === 'sidepanel' && item.primary), 'sidepanel is recommended')
assert.equal(
  TOOLKIT_CATALOG.filter((item) => (item.id as string) === 'email-compose').length,
  0,
  'email compose removed'
)

const palette = readFileSync(resolve(root, '../content/toolkit-palette.ts'), 'utf8')
assert.match(palette, /搜索工具/, 'palette is searchable overlay')

const background = readFileSync(resolve(root, '../entrypoints/background.ts'), 'utf8')
assert.match(background, /openToolkitPage/, 'open-toolkit opens options toolkit tab')

console.log('toolkit-catalog self-check ok')
