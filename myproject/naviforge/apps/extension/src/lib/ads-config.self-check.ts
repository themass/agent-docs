import assert from 'node:assert/strict'

import {
  AD_EMBED_BASE_URL,
  AD_ENABLED_SURFACES,
  adEmbedUrl,
  adsEnabled,
  surfaceAdsEnabled,
} from './ads-config.js'

assert.equal(AD_EMBED_BASE_URL, '')
assert.equal(adEmbedUrl('options'), null)
assert.equal(adsEnabled('options'), false)
assert.equal(adsEnabled('agentThinking'), false)
assert.deepEqual([...AD_ENABLED_SURFACES], ['options', 'ocr', 'screenshot'])

const base = 'https://example.test/ads/'
assert.equal(surfaceAdsEnabled('options', base, AD_ENABLED_SURFACES), true)
assert.equal(surfaceAdsEnabled('ocr', base, AD_ENABLED_SURFACES), true)
assert.equal(surfaceAdsEnabled('screenshot', base, AD_ENABLED_SURFACES), true)
assert.equal(surfaceAdsEnabled('agentFeed', base, AD_ENABLED_SURFACES), false)
assert.equal(surfaceAdsEnabled('agentThinking', base, AD_ENABLED_SURFACES), false)
assert.equal(surfaceAdsEnabled('options', '  ', AD_ENABLED_SURFACES), false)
assert.equal(surfaceAdsEnabled('agentFeed', base, ['agentFeed']), true)

console.log('ads-config.self-check ok')
