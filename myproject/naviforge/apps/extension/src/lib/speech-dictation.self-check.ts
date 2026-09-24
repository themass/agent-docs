import assert from 'node:assert/strict'

import { readSpeechLangConfig } from './speech-lang.js'
import {
  browserTagToSpeechLang,
  detectSpeechLangFromText,
  localeToSpeechLang,
  resolveSpeechRecognitionLang,
  stripLeadingLatinBeforeCjk,
} from './speech-dictation.js'

assert.equal(localeToSpeechLang('zh-CN'), 'zh-CN')
assert.equal(localeToSpeechLang('en'), 'en-US')
assert.equal(browserTagToSpeechLang('en-GB'), 'en-US')
assert.equal(detectSpeechLangFromText('你好世界'), 'zh-CN')
assert.equal(detectSpeechLangFromText('hello world'), 'en-US')
assert.equal(
  resolveSpeechRecognitionLang({
    config: { mode: 'fixed', targets: ['zh-CN'], fixed: 'zh-CN' },
    languages: ['en-US'],
  }),
  'zh-CN'
)
assert.equal(
  resolveSpeechRecognitionLang({
    config: { mode: 'auto', targets: ['zh-CN', 'en-US'], fixed: 'zh-CN' },
    hintText: 'hello there',
    languages: ['zh-CN'],
  }),
  'en-US',
  'latin hint picks english when in targets'
)
assert.equal(
  resolveSpeechRecognitionLang({
    config: { mode: 'auto', targets: ['zh-CN', 'en-US'], fixed: 'zh-CN' },
    languages: ['en-US'],
    lastSpeechLang: 'en-US',
  }),
  'zh-CN',
  'auto prefers first target over stale en last-lang'
)
assert.equal(stripLeadingLatinBeforeCjk('no no你好'), '你好')
assert.deepEqual(
  readSpeechLangConfig({ speechLang: 'zh-CN' }).mode,
  'fixed',
  'legacy single lang migrates to fixed'
)
assert.deepEqual(
  readSpeechLangConfig({ speechLangMode: 'auto', speechTargets: ['en-US', 'ja-JP'] }).targets,
  ['en-US', 'ja-JP']
)

console.log('speech-dictation self-check ok')
