import {
  collectMediaFeedTitlesFromParts,
  extractPageList,
  isLikelyVideoEntryTitle,
  parseIndexedSnapshotLines,
} from './index.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const legacy = extractPageList({
  snapshotContent: '[1] link "Video A"\n[2] link "Video B"\n[3] button "Go"',
  mediaHints: [{ url: 'https://cdn/x.m3u8', kind: 'hls' }],
})
assert(legacy.length >= 2 && legacy[0].mediaUrls.length === 1, 'extract merge legacy')

const bwqdtViewport = [
  '*[0]<a  />',
  'bwqdt.cc',
  '*[13]<div >在线电影',
  '短视频区',
  '*[24]<img />',
  'HD',
  '0:28:55',
  '从零实现一个浏览器 Agent',
  '站点官方 · 17.0万次观看',
].join('\n')

const spa = extractPageList({
  snapshotContent: bwqdtViewport,
  pageUrl: 'https://bwqdt.cc/home',
})
assert(
  spa.some((item) => item.title.includes('Agent') || item.title.includes('浏览器')),
  `bwqdt-shaped snapshot should yield video title, got: ${spa.map((i) => i.title).join('|')}`
)
assert(!spa.some((item) => item.title === 'bwqdt.cc'), 'site chrome title filtered')

const chipsOnly = extractPageList({
  snapshotContent: ['*[6]<div >热销专题', '重口味', '捆绑诱饵带'].join('\n'),
  pageUrl: 'https://example.test/home',
})
assert(chipsOnly.length === 0, 'category chips alone should not become list items')

const indexed = parseIndexedSnapshotLines('[13]<div >在线电影\n短视频区')
assert(indexed[0]?.index === 13, 'indexed parse')

assert(isLikelyVideoEntryTitle('从零实现一个浏览器 Agent'), 'video title heuristic')
assert(!isLikelyVideoEntryTitle('重口味'), 'chip not video title')

const durationBlock = collectMediaFeedTitlesFromParts(
  { content: ['HD', '0:28:55', '三分钟看懂扩散模型'].join('\n') },
  5
)
assert(durationBlock.some((t) => t.includes('扩散')), durationBlock.join('|'))

console.log('extract self-check ok')
