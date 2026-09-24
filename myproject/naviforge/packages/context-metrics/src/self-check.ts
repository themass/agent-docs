import assert from 'node:assert/strict'

import { buildContextBreakdown, contextUsageRatio, estimateTokens } from './build.js'

assert.equal(estimateTokens('abcd'), 2)

const breakdown = buildContextBreakdown({
  system: 'kernel',
  blocks: [
    { id: 'task', label: 'Task', text: 'summarize page' },
    { id: 'snapshot', label: 'Snapshot', text: 'x'.repeat(4000) },
    { id: 'trace', label: 'Trace', text: 'step 1' },
  ],
  limitInputTokens: 32_000,
  runTokenBudget: 200_000,
  runTotalTokens: 12_000,
  pressured: false,
  compaction: { beforeTokens: 28_000, afterTokens: 11_000, coveredRecords: 40 },
})

assert.ok(breakdown.grandTotalTokens > breakdown.systemTokens)
assert.ok(contextUsageRatio(breakdown) < 1)
assert.equal(breakdown.compaction?.coveredRecords, 40)

console.log('context-metrics self-check ok')
