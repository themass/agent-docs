import assert from 'node:assert/strict'

import {
  blockedOcrModelHint,
  clampPixelCrop,
  cssRectToPixels,
  formatOcrError,
  formatOcrMarkdown,
  isBrowserPdfUrl,
  MIN_CROP_CSS_PX,
} from './vision-ocr-core'
import { isBlockedOcrModel } from './llm-profiles'

assert.equal(MIN_CROP_CSS_PX, 8)
assert.deepEqual(cssRectToPixels({ x: 10, y: 20, width: 100, height: 50 }, 2), {
  x: 20,
  y: 40,
  width: 200,
  height: 100,
})
assert.deepEqual(clampPixelCrop({ x: -10, y: 10, width: 500, height: 20 }, 200, 100), {
  x: 0,
  y: 10,
  width: 200,
  height: 20,
})
assert.equal(isBlockedOcrModel('deepseek-v4-flash'), true)
assert.equal(isBlockedOcrModel('deepseek-v4-pro'), true)
assert.equal(isBlockedOcrModel('doubao-seed-1.6-vision'), false)
assert.equal(isBlockedOcrModel('qwen3.5-ocr'), false)
assert.equal(isBlockedOcrModel('mt-claude-sonnet-4-6'), false)
assert.equal(isBlockedOcrModel('doubao-seedream-4.0'), true)
assert.ok(blockedOcrModelHint('deepseek-v4-flash').includes('不能看图'))
assert.equal(
  formatOcrError(new Error('LLM HTTP 400: invalid image content')),
  '当前 OCR 模型不接受图片，请换成 qwen3.5-ocr、豆包 vision 或 Claude Sonnet'
)
assert.equal(formatOcrError(new Error('network down')), 'network down')
assert.equal(isBrowserPdfUrl('https://example.com/doc.pdf'), true)
assert.equal(isBrowserPdfUrl('https://example.com/doc.pdf?download=1'), true)
assert.equal(isBrowserPdfUrl('https://example.com/readme.md'), false)
assert.equal(
  isBrowserPdfUrl('chrome-extension://mhjfbmdgcfjbbpaeojofohoefgiehjai/index.html'),
  true
)

assert.equal(
  formatOcrMarkdown('顾问名单', 'https://example.com/a'),
  '# OCR\n\nSource: https://example.com/a\n\n顾问名单\n'
)

console.log('vision-ocr self-check ok')
