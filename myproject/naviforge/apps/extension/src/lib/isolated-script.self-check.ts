import assert from 'node:assert/strict'

import { isPageCspEvalError, runIsolatedScript, serializeScriptResult } from './isolated-script.js'

const ok = await runIsolatedScript('return [1,2,3].map((n) => n * 2)')
assert(ok.ok && Array.isArray(ok.result) && (ok.result as number[])[2] === 6, 'async return')

const denied = await runIsolatedScript('')
assert(!denied.ok, 'empty script')

assert(isPageCspEvalError("Evaluating a string as JavaScript violates CSP"), 'detect github CSP')
assert(!isPageCspEvalError('timeout after 15000ms'), 'timeout is not CSP')

const big = serializeScriptResult({ x: 'y'.repeat(60_000) })
assert(
  typeof big === 'object' && big !== null && '__truncated' in big,
  'truncate big result'
)

console.log('isolated-script self-check ok')
