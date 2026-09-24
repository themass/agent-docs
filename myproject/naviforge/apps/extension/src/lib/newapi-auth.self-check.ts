import assert from 'node:assert/strict'

import {
  authCallbackUrl,
  buildNewApiLoginUrl,
  normalizeNewApiAuthState,
  parseNewApiCallbackTokens,
  shouldSyncBootstrap,
} from './newapi-auth.js'

// Mock chrome for node self-check
const g = globalThis as { chrome?: { runtime: { id: string } } }
g.chrome = { runtime: { id: 'testextid' } }

const callback = authCallbackUrl()
assert.match(callback, /^https:\/\/testextid\.chromiumapp\.org\/auth-callback$/)
assert.match(buildNewApiLoginUrl(), /extension_id=testextid&client=naviforge-extension/)

const tokens = parseNewApiCallbackTokens(
  'https://example/auth-callback.html?token=abc&refresh=def&expires_in=3600'
)
assert.deepEqual(tokens, { accessToken: 'abc', refreshToken: 'def', expiresInSec: 3600 })

assert.equal(
  parseNewApiCallbackTokens('https://x/#access_token=hash')?.accessToken,
  'hash'
)

const managed = normalizeNewApiAuthState({ mode: 'managed', accessToken: 't' })
assert.equal(shouldSyncBootstrap(managed, { force: false, apiKeyEmpty: true }), true)
assert.equal(
  shouldSyncBootstrap({ ...managed, lastSyncAt: Date.now() }, { apiKeyEmpty: false }),
  false
)

console.log('newapi-auth self-check ok')
