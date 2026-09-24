import assert from 'node:assert/strict'

import { formatTranslationFeedback, translateTextsGtx } from './page-translate'

{
  const empty = await translateTextsGtx(['', '  '], 'zh-CN')
  assert.deepEqual(empty, ['', '  '], 'blank strings pass through')
}

assert.match(
  formatTranslationFeedback({ mode: 'gtx', translated: 500, limited: true, lang: 'zh-CN' }),
  /已译成中文.*仅前 500 段/
)
assert.match(formatTranslationFeedback({ mode: 'gtx', translated: 12, lang: 'en' }), /已译成English/)
assert.match(formatTranslationFeedback({ mode: 'restore', translated: 3 }), /已还原原文/)

console.log('page-translate self-check ok')
