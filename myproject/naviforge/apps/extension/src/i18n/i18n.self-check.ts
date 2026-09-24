import assert from 'node:assert/strict'

import { catalogs } from './catalogs'
import { LOCALES, resolveLocale } from './locales'
import { t } from './t'

assert.equal(resolveLocale('auto', ['fr-FR', 'de']), 'en', 'unknown browser language falls back to English')
assert.equal(resolveLocale('auto', []), 'en')
assert.equal(resolveLocale('auto', ['zh-TW']), 'zh-CN')
assert.equal(resolveLocale('auto', ['es-MX', 'en']), 'es')
assert.equal(resolveLocale('auto', ['en-GB']), 'en')
assert.equal(resolveLocale('zh-CN', ['en']), 'zh-CN', 'manual override wins')

function keys(obj: unknown, prefix = ''): string[] {
  if (!obj || typeof obj !== 'object') return []
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    typeof v === 'string' ? [`${prefix}${k}`] : keys(v, `${prefix}${k}.`)
  )
}

const enKeys = keys(catalogs.en)
for (const locale of LOCALES) {
  assert.deepEqual(keys(catalogs[locale]), enKeys, `${locale} catalog keys match en`)
}

assert.equal(t('popup.workspace', undefined, 'en'), 'Open workspace')
assert.equal(t('missing.key', undefined, 'en'), 'missing.key')
assert.ok(t('chat.actingFallback', { label: 'dom_click' }, 'en').includes('dom_click'))

console.log('i18n self-check ok')
