import { expect, test } from '@playwright/test'

import { collectCandidates, extractContent } from '../../apps/extension/src/lib/content-extract'
import {
  deliverablePlanMilestone,
  resolveDeliverable,
} from '../../packages/runtime/src/deliverable.js'
import { pickFeedClickIndex } from '../../packages/runtime/src/media-feed-deterministic.js'
import {
  classifyPageState,
  enrichItemsWithSnapshotFeed,
  formatPageState,
} from '../../packages/runtime/src/page-state.js'
import type { DomSnapshot } from '@naviforge/dom-plane'

const CASE1_TASK = '分析这个页面的视频名称和源地址'
const CASE2_TASK =
  '分析这个网站的 视频列表，给我生成一个python 脚本，抓取每个分类下的第一页。\n页码可以定义多少页，默认值为1'

test.describe('golden browser agent — deliverable plans (G1/G2)', () => {
  test('G2 script task locks script deliverable and 4-step PLAN', () => {
    expect(resolveDeliverable(CASE2_TASK)).toBe('script')
    const plan = deliverablePlanMilestone('script')
    expect(plan).toMatch(/script_save/)
    expect(plan).toMatch(/pages 默认 1/)
    expect(plan).toMatch(/禁止 media_extract recipe/)
  })

  test('G1 media task locks media deliverable and click→network PLAN', () => {
    expect(resolveDeliverable(CASE1_TASK)).toBe('media')
    const plan = deliverablePlanMilestone('media')
    expect(plan).toMatch(/click_index/)
    expect(plan).toMatch(/network/)
    expect(plan).toMatch(/m3u8/)
  })
})

test.describe('golden browser agent — page state on test-site', () => {
  test('G1 video-feed: structured extract + snapshot indices → list + feed_clicks', async ({
    page,
  }) => {
    await page.goto('/fixtures/video-feed.html')
    const url = 'http://127.0.0.1:4177/fixtures/video-feed.html'
    const extracted = extractContent(await page.evaluate(collectCandidates), { url, n: 4 })
    expect(extracted.items.length).toBeGreaterThanOrEqual(2)

    const snap: DomSnapshot = {
      revision: 1,
      url,
      title: 'Video feed fixture',
      header: '*[1] 首页 *[2] 登录',
      content: extracted.items
        .map((item, i) => `*[${30 + i}] ${item.title}`)
        .join('\n'),
      footer: '',
    }

    const items = enrichItemsWithSnapshotFeed(
      extracted.items.map((item) => ({ title: item.title, url: item.url })),
      snap
    )
    const state = classifyPageState({
      url,
      title: snap.title,
      login: false,
      blocking: false,
      items,
    })
    expect(state.role).toBe('list')
    expect(formatPageState(state)).toMatch(/feed_clicks:/)
    expect(formatPageState(state)).toMatch(/click_index=30/)
    expect(pickFeedClickIndex(snap, state)).toBe(30)
  })

  test('G1 SPA-style empty extract: snapshot indices alone yield list role', () => {
    const snap: DomSnapshot = {
      revision: 1,
      url: 'https://example.test/feed',
      title: 'feed',
      header: '*[3] 登录',
      content: ['*[12] 三分钟看懂扩散模型', '*[13] 从零实现一个浏览器 Agent'].join('\n'),
      footer: '',
    }
    const items = enrichItemsWithSnapshotFeed([], snap)
    const state = classifyPageState({
      url: snap.url,
      title: snap.title,
      login: false,
      blocking: false,
      items,
    })
    expect(state.role).toBe('list')
    expect(pickFeedClickIndex(snap, state)).toBe(12)
  })

  test('G1 media-harvest-lab: play button fetches m3u8 (click→network path)', async ({ page }) => {
    await page.goto('/fixtures/video-detail.html?title=golden-case')
    const m3u8 = page.waitForResponse((res) => res.url().includes('master.m3u8'))
    await page.getByRole('button', { name: '播放' }).click()
    const res = await m3u8
    expect(res.ok()).toBeTruthy()
  })
})
