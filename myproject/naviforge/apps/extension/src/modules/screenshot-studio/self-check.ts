import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { ensureDrawKit, listShapeTypes } from './editor/draw-kit/index.js'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')

const index = readFileSync(resolve(root, 'modules/screenshot-studio/index.ts'), 'utf8')
assert.match(index, /launchScreenshotStudio/, 'exports launchScreenshotStudio')
assert.match(index, /ScreenshotEditor/, 'exports ScreenshotEditor')

const launch = readFileSync(resolve(root, 'modules/screenshot-studio/capture/launch.ts'), 'utf8')
assert.match(launch, /screenshot-studio\.html/, 'launch opens studio page')

const render = readFileSync(resolve(root, 'modules/screenshot-studio/editor/render-export.ts'), 'utf8')
assert.doesNotMatch(render, /if \(item\.type ===/, 'render uses shape registry not switches')

ensureDrawKit()
const types = listShapeTypes()
assert.ok(types.includes('ellipse'), 'draw-kit includes ellipse')
assert.ok(types.includes('highlighter'), 'draw-kit includes highlighter')
assert.ok(types.includes('marker'), 'draw-kit includes marker')
assert.ok(types.includes('blur'), 'draw-kit includes blur')
assert.ok(types.includes('sticker'), 'draw-kit includes sticker')

const readme = readFileSync(resolve(root, 'modules/screenshot-studio/editor/draw-kit/README.md'), 'utf8')
assert.match(readme, /registerShapeDefinition/, 'draw-kit documents registry pattern')

console.log('screenshot-studio self-check ok')
