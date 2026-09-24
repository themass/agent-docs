import assert from 'node:assert/strict'

import { assertTracerouteTarget, runSystemTraceroute } from './traceroute.js'

assert.equal(assertTracerouteTarget('1.1.1.1'), '1.1.1.1')
assert.equal(assertTracerouteTarget(' example.com '), 'example.com')
assert.throws(() => assertTracerouteTarget('https://evil'), /hostname/)
assert.throws(() => assertTracerouteTarget('a/b'), /hostname/)

// Smoke: command must exist on this machine; skip soft-fail if missing.
try {
  const result = await runSystemTraceroute('127.0.0.1', 2, 8_000)
  assert.ok(result.lines.length >= 1, 'traceroute returns lines')
  assert.match(result.command, /traceroute|tracert/)
  console.log('host traceroute self-check ok')
} catch (error) {
  if (/failed to start/.test((error as Error).message)) {
    console.log('host traceroute self-check skipped (binary missing)')
  } else {
    throw error
  }
}
