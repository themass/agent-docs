import assert from 'node:assert/strict'

import type { DomSnapshot } from '@naviforge/dom-plane'

import { extractFeedLabelsFromSnapshot, formatFeedEvidenceNote } from './page-feed-evidence.js'
import { taskNeedsNetworkPlane } from './media-harvest-hooks.js'
import { pickFeedClickIndex } from './media-feed-deterministic.js'
import { resolveDeliverable } from './deliverable.js'

const snap: DomSnapshot = {
  revision: 1,
  url: 'https://example.test/home',
  title: 'feed',
  header: '热销专区',
  content: [
    '*[12] 第一集：开场',
    '*[13] 第二集：转折',
    '*[14] 第三集：结局',
    '登录',
    '***',
  ].join('\n'),
  footer: '',
}

const labels = extractFeedLabelsFromSnapshot(snap)
assert.ok(labels.length >= 3, 'feed labels from snapshot')
assert.ok(labels.some((l) => l.includes('第一集')), labels.join('|'))
assert.ok(formatFeedEvidenceNote(labels).startsWith('EVIDENCE: PAGE FEED'))

assert.equal(pickFeedClickIndex(snap), 12)

assert.equal(taskNeedsNetworkPlane(resolveDeliverable('分析视频源地址')), true)
assert.equal(
  taskNeedsNetworkPlane(resolveDeliverable('给我 python 脚本抓取视频列表')),
  false,
  'script deliverable must not require debugger preflight'
)
assert.equal(taskNeedsNetworkPlane(resolveDeliverable('标记top3')), false)
assert.equal(taskNeedsNetworkPlane(resolveDeliverable('总结本页')), false)

console.log('golden-media-harvest.self-check ok')
