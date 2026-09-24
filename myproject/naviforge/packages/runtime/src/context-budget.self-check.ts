import assert from 'node:assert/strict'

import { CONTEXT_BUDGET_RATIOS, inputTokenRatio, l1ProjectionCap } from './context-budget.js'

assert.equal(l1ProjectionCap(32_000, 0.5), 32_000)
assert.equal(l1ProjectionCap(32_000, 0.7), 16_000)
assert.ok(l1ProjectionCap(32_000, 0.85) < 12_000)

const ratio = inputTokenRatio({
  system: 'x'.repeat(80_000),
  user: 'y'.repeat(80_000),
  toolsTokens: 0,
  maxInputTokens: 32_000,
})
assert.ok(ratio >= CONTEXT_BUDGET_RATIOS.hard)

console.log('context-budget self-check ok')
