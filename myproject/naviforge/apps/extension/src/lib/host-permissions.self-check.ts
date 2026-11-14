import assert from 'node:assert/strict'

import { isHttpPageUrl, originPatternForUrl } from './host-permissions.js'

assert.equal(originPatternForUrl('https://swasnext.console.aliyun.com/servers'), 'https://swasnext.console.aliyun.com/*')
assert.equal(originPatternForUrl('chrome://extensions'), null)
assert.equal(isHttpPageUrl('https://example.com'), true)
assert.equal(isHttpPageUrl('chrome://newtab'), false)

console.log('host-permissions self-check ok')
