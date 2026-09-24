import assert from 'node:assert/strict'

import { minePageSignals } from '@naviforge/observe'

import {
  isMediaEvidenceTask,
  tryMediaPlaybackDeterministicResult,
} from './page-signals-hydrate.js'

const avdt = `window.$avdt = {"hls":"2026/08/18/x/index.m3u8?t=1","cdns":["cdn22.jiuse3.cloud"]}`
const bundle = minePageSignals({
  url: 'https://example.com/v',
  title: 't',
  inlineScripts: [avdt],
  externalScriptSrcs: [],
  meta: [],
  resources: [],
})

assert(isMediaEvidenceTask('分析一下这个页面视频的播放地址'))
assert(
  tryMediaPlaybackDeterministicResult(bundle, '分析一下这个页面视频的播放地址')?.includes('cdn22.jiuse3.cloud'),
  'media deterministic includes resolved url'
)

const multiCdn = minePageSignals({
  url: 'https://example.com/v',
  title: 't',
  inlineScripts: [
    `window.$avdt = {"hls":"path/index.m3u8","cdns":["cdn-a.example","cdn-b.example"]}`,
  ],
  externalScriptSrcs: [],
  meta: [],
  resources: [],
})
assert.equal(
  tryMediaPlaybackDeterministicResult(multiCdn, '分析播放地址'),
  undefined,
  'F6: ambiguous multi-CDN should not auto-complete'
)

console.log('page-signals-hydrate self-check ok')
