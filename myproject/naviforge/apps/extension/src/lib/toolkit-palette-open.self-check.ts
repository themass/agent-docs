import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')

const launch = readFileSync(resolve(root, 'lib/surface-launch.ts'), 'utf8')
assert.doesNotMatch(
  launch,
  /openPageToolList[\s\S]*runtime\.sendMessage/,
  'openPageToolList must not sendMessage to background (SW cannot receive own messages)'
)

const palette = readFileSync(resolve(root, 'lib/toolkit-palette-open.ts'), 'utf8')
assert.match(palette, /tabs\.sendMessage/, 'palette opens via content script message')

console.log('toolkit-palette-open self-check ok')
