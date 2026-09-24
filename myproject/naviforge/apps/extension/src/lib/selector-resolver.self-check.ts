import assert from 'node:assert/strict'

import type { PageController } from '@page-agent/page-controller'

import { readSelectorMap, selectorEntriesFromMap } from './selector-resolver.js'

const map = new Map([[1, { ref: { tag: 'button' } }]])
const pc = { selectorMap: map } as unknown as PageController

assert.equal(readSelectorMap(pc)?.size, 1)
assert.equal(readSelectorMap({} as PageController), undefined)

let fallback = false
const entries = selectorEntriesFromMap({} as PageController, () => {
  fallback = true
  return [{ index: 9, element: {} as Element }]
})
assert.ok(fallback, 'falls back when selectorMap missing')
assert.equal(entries[0]?.index, 9)

console.log('selector-resolver self-check ok')
