import assert from 'node:assert/strict'

import {
  compactReadableText,
  githubRawReadmeUrl,
  isFullPageSnapshotHeader,
  pageHeadingFromTitle,
  parseGithubRepoPath,
  pickPreferredReadChars,
  snapshotTruncationHint,
  stripChromePrefix,
} from './read-page-core'

const long = 'a'.repeat(30_000)
const packed = compactReadableText(long, 1000)
assert(packed.truncated && packed.text.endsWith('(truncated)'), 'compacts long text')

assert.equal(parseGithubRepoPath('/duongductrong/Snapzy')?.repo, 'Snapzy')
assert.equal(parseGithubRepoPath('/trending'), null)

assert.equal(
  githubRawReadmeUrl('https://github.com/duongductrong/Snapzy'),
  'https://raw.githubusercontent.com/duongductrong/Snapzy/HEAD/README.md'
)

assert.equal(isFullPageSnapshotHeader('(full page):'), true)
assert(snapshotTruncationHint('(full page):').includes('read_page'), 'full page hint')

assert.equal(pageHeadingFromTitle('模型列表--豆包语音-火山引擎'), '模型列表')
assert.equal(pickPreferredReadChars([200, 8_000, 24_000], 24_000), 8_000)
assert.equal(pickPreferredReadChars([24_000], 24_000), 24_000)

const chrome = `文档中心
账号ID : 2100917825
可用余额
¥ 198.06
退出登录
豆包语音
产品动态
模型列表
音色列表
文档首页
豆包语音
产品概述
模型列表
复制全文
模型列表
本文档汇总火山语音各产品线的可用模型及其支持的功能与参数`
const stripped = stripChromePrefix(chrome, '模型列表--豆包语音-火山引擎')
assert(stripped.startsWith('模型列表\n本文档汇总'), 'strips chrome before article heading')
assert(!stripped.includes('账号ID'), 'drops account chrome')

console.log('read-page-core self-check ok')
