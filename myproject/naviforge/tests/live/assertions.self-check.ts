import assert from 'node:assert/strict'

import { assessExtractedItems, classifyEnvironmentBlock } from './assertions.js'

const bilibili = {
  id: 'bilibili-knowledge',
  name: 'Bilibili 知识频道',
  url: 'https://www.bilibili.com/c/knowledge/',
  detailUrl: /\/video\//,
  forbiddenTitle:
    /^(稍后再看|收藏|分享|热门|首页|watch later|save|share|more actions?)$/i,
}

assert.deepEqual(
  assessExtractedItems(
    [
      { title: '浏览器 Agent 实战', url: 'https://www.bilibili.com/video/BV123' },
      { title: '扩散模型详解', url: 'https://www.bilibili.com/video/BV456' },
      { title: 'Rust 所有权', url: 'https://www.bilibili.com/video/BV789' },
    ],
    bilibili,
    3
  ),
  []
)

const broken = assessExtractedItems(
  [
    { title: '稍后再看', url: 'https://www.bilibili.com/video/BV123' },
    { title: '稍后再看', url: 'https://www.bilibili.com/video/BV123' },
    { title: '[7]<a >错误标题 />', url: 'https://www.bilibili.com/' },
  ],
  bilibili,
  3
)
assert(broken.some((item) => item.code === 'control_title'))
assert(broken.some((item) => item.code === 'duplicate_url'))
assert(broken.some((item) => item.code === 'wrong_detail_url'))
assert(broken.some((item) => item.code === 'snapshot_title'))

assert.equal(classifyEnvironmentBlock('Verify you are human'), 'ENV_BLOCKED')
assert.equal(classifyEnvironmentBlock('正常内容页面'), undefined)

console.log('live assertions self-check ok')
