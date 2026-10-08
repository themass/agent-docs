import assert from 'node:assert/strict'

import type { DomSnapshot } from '@naviforge/dom-plane'

import {
  collectMediaFeedTitles,
  formatMediaHomeHarvestResult,
  isLikelyVideoEntryTitle,
  isTopicBucketSnapshotTitle,
  mediaRowsFromPageState,
  pickFeedClickIndex,
  pickHomeExploreClickIndex,
} from './media-home-harvest.js'
import { classifyPageState, type PageStateItem } from './page-state.js'

assert.equal(isTopicBucketSnapshotTitle('<div >热销专题'), true)
assert.equal(isTopicBucketSnapshotTitle('精品推荐'), true)
assert.equal(isTopicBucketSnapshotTitle('三分钟看懂扩散模型'), false)

assert.equal(isLikelyVideoEntryTitle('重口味'), false)
assert.equal(isLikelyVideoEntryTitle('捆绑诱饵带'), false)
assert.equal(isLikelyVideoEntryTitle('从零实现一个浏览器 Agent'), true)
assert.equal(isLikelyVideoEntryTitle('欲求未满的继姐在房间用假屌来抽插'), true)

const spaSnap: DomSnapshot = {
  revision: 1,
  url: 'https://example.test/home',
  title: 'home',
  header: '',
  content: [
    '*[10]<div >热销专题',
    '重口味',
    '*[20] 露娜姐姐',
    '*[21] 日本知名母狗',
    '*[22] 欧美狐狸姐',
  ].join('\n'),
  footer: '',
}

assert.equal(pickFeedClickIndex(spaSnap), 20)

const sectionSnap: DomSnapshot = {
  ...spaSnap,
  content: ['*[13]<div >在线电影', '*[14]<div >有声小说'].join('\n'),
}
assert.equal(pickHomeExploreClickIndex(sectionSnap), 13)

const homepageCards: DomSnapshot = {
  ...spaSnap,
  content: [
    '*[13]<div >在线电影',
    '*[23]<img />',
    '*[24]<img />',
    'HD',
    '0:28:55',
    '从零实现一个浏览器 Agent',
    '站点官方 · 17.0万次观看',
    '*[25]<img />',
  ].join('\n'),
}
assert.equal(pickFeedClickIndex(homepageCards), 24)
assert.equal(
  pickFeedClickIndex(sectionSnap, {
    url: sectionSnap.url,
    title: sectionSnap.title,
    role: 'list',
    blocked: false,
    items: [{ title: '从零实现一个浏览器 Agent', clickIndex: 42 }],
  }),
  42,
  'PAGE STATE media card must outrank a category nav when snapshot text is sparse'
)

const feedSnap: DomSnapshot = {
  ...spaSnap,
  content: [
    'Current Page: home',
    '重口味',
    '捆绑诱饵带',
    '从零实现一个浏览器 Agent',
    '三分钟看懂扩散模型',
  ].join('\n'),
}

const titles = collectMediaFeedTitles(feedSnap, 10)
assert.ok(!titles.some((t) => t === '重口味'), titles.join('|'))
assert.ok(titles.some((t) => t.includes('扩散') || t.includes('Agent')), titles.join('|'))

const durationSnap: DomSnapshot = {
  ...spaSnap,
  content: ['HD', '0:28:55', '从零实现一个浏览器 Agent', '猫咪官方 · 17.0万次观看'].join('\n'),
}
const fromDuration = collectMediaFeedTitles(durationSnap, 5)
assert.ok(fromDuration.some((t) => t.includes('Agent')), fromDuration.join('|'))

const formatted = formatMediaHomeHarvestResult({
  rows: [{ title: 'A', pageUrl: 'https://example.test/v/1' }],
  shortfall: '未能捕获 m3u8',
})
assert.match(formatted, /shortfall:/)
assert.match(formatted, /^1\. A/m)
assert.match(formatted, /页面:/)

const bwqdtItems: PageStateItem[] = [
  { title: '[10]<div >热销专题', clickIndex: 10 },
  { title: '偷情朋友老婆酒店实录，奶大穴紧太爽！', clickIndex: 61 },
  {
    title: '白皙女大生粉嫩小穴被粗壮大屌猛顶到不停收缩痉挛，泰国极品美女湿滑紧致狂野迎合，淫水横流高潮迭起',
    clickIndex: 63,
  },
]
const bwqdtState = classifyPageState({
  url: 'https://example.test/home',
  title: 'home',
  login: false,
  blocking: false,
  items: bwqdtItems,
})
const fromPageState = mediaRowsFromPageState(bwqdtState, 8)
assert.equal(fromPageState.length, 2, fromPageState.map((r) => r.title).join('|'))
assert.equal(fromPageState[0]?.clickIndex, 61)

console.log('media-home-harvest.self-check ok')
