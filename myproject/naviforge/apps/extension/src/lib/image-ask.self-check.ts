import assert from 'node:assert/strict'

import {
  IMAGE_ASK_DEFAULT_QUESTION,
  isAllowedImageFile,
  MAX_IMAGE_BYTES,
  shotAskFromText,
} from './image-ask'

assert.equal(shotAskFromText('刚才的截图里手机号是多少')?.kind, 'latest')
assert.equal(shotAskFromText('看看截图上写了什么')?.kind, 'latest')
assert.equal(shotAskFromText('分析一下上次截图')?.kind, 'latest')
assert.equal(
  shotAskFromText('shots/20260814T120000Z-visible-abc.png 里有什么')?.kind,
  'path'
)
assert.deepEqual(shotAskFromText('看 shots/foo.png'), {
  kind: 'path',
  path: 'shots/foo.png',
})
assert.equal(shotAskFromText('帮我截图保存到工作区'), null)
assert.equal(shotAskFromText('全页截图'), null)
assert.equal(shotAskFromText('滚动截图这一页'), null)
assert.equal(shotAskFromText('take a screenshot of this page'), null)
assert.equal(shotAskFromText('打开淘宝搜耳机'), null)
assert.equal(shotAskFromText('分析这种图片，找出手机号'), null)
assert.ok(IMAGE_ASK_DEFAULT_QUESTION.includes('看不清'))
assert.ok(
  isAllowedImageFile({ name: 'a.png', type: 'image/png', size: 12 }),
  'png ok'
)
assert.ok(!isAllowedImageFile({ name: 'a.svg', type: 'image/svg+xml', size: 12 }))
assert.ok(!isAllowedImageFile({ name: 'a.png', type: 'image/png', size: MAX_IMAGE_BYTES + 1 }))

console.log('image-ask self-check ok')
