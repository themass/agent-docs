import assert from 'node:assert/strict'

import { minePageSignals } from '@naviforge/observe'

import { classifyPageBrief, urlMatchesDetailShape } from './page-role.js'
import { parseDiscoverPayload } from './discover.js'
import { selectCatalogStrategy, wantsMultipleMediaItems } from './strategy.js'

const listDiscover = parseDiscoverPayload({
  url: 'https://example.com/vod/type/id/1.html',
  origin: 'https://example.com',
  sections: [],
  pagination: [],
  detailShape: 'index.php/vod/play/id/*',
  listSample: [
    { title: 'A', url: 'https://example.com/index.php/vod/play/id/1/sid/1/nid/1.html' },
    { title: 'B', url: 'https://example.com/index.php/vod/play/id/2/sid/1/nid/1.html' },
    { title: 'C', url: 'https://example.com/index.php/vod/play/id/3/sid/1/nid/1.html' },
  ],
})!

const playUrl = 'https://example.com/index.php/vod/play/id/331448/sid/1/nid/1.html'
const playBundle = minePageSignals({
  url: playUrl,
  title: 'play',
  inlineScripts: [`var player_aaaa = {"url":"https://cdn.example/a.m3u8","flag":"play"}`],
  externalScriptSrcs: [],
  meta: [],
  resources: [],
})

const playDiscover = parseDiscoverPayload({
  url: playUrl,
  origin: 'https://example.com',
  sections: [{ name: 'Cat', url: 'https://example.com/search?q=x' }],
  pagination: [],
  detailShape: 'index.php/vod/play/id/*',
  listSample: [
    { title: 'rel1', url: 'https://example.com/index.php/vod/play/id/1/sid/1/nid/1.html' },
    { title: 'rel2', url: 'https://example.com/index.php/vod/play/id/2/sid/1/nid/1.html' },
    { title: 'rel3', url: 'https://example.com/index.php/vod/play/id/3/sid/1/nid/1.html' },
  ],
})!

assert.ok(
  urlMatchesDetailShape(playUrl, 'index.php/vod/play/id/*'),
  'detail shape matches play pathname'
)
assert.ok(!urlMatchesDetailShape(listDiscover.url, 'index.php/vod/play/id/*'), 'list url not detail item')

const listBrief = classifyPageBrief(listDiscover, null)
assert.equal(listBrief.role, 'list', 'category page → list role')

const playBrief = classifyPageBrief(playDiscover, playBundle)
assert.equal(playBrief.role, 'play', 'play page with playback signal → play role')

const task = '抓取当前页面下所有的视频源地址和名称'
assert.ok(wantsMultipleMediaItems(task))
assert.equal(
  selectCatalogStrategy({
    task,
    brief: listBrief,
    fullSiteCrawl: false,
    wantsMedia: true,
  }),
  'spawn-media'
)
assert.equal(
  selectCatalogStrategy({
    task,
    brief: playBrief,
    fullSiteCrawl: false,
    wantsMedia: true,
  }),
  'media-extract'
)
assert.equal(
  selectCatalogStrategy({
    task: '分析所有博客分类',
    brief: listBrief,
    fullSiteCrawl: true,
    wantsMedia: false,
  }),
  'full-catalog'
)

console.log('page-role/strategy self-check ok')
