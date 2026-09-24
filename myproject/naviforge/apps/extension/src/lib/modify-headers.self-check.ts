import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../../')
const wxt = readFileSync(resolve(root, 'wxt.config.ts'), 'utf8')
const modify = readFileSync(resolve(root, 'src/lib/modify-headers.ts'), 'utf8')

assert.doesNotMatch(wxt, /nativeMessaging/, 'nativeMessaging removed from manifest')
assert.doesNotMatch(wxt, /pagead2\.googlesyndication/, 'AdSense script must not be in extension CSP')
assert.match(wxt, /frame-src http: https:/, 'ad iframe hosts allowed')
assert.match(modify, /enabled: false/, 'Modify Header defaults off')
assert.match(modify, /persistModifyHeadersSettings/, 'persist helper exists')

console.log('modify-headers compliance self-check ok')
