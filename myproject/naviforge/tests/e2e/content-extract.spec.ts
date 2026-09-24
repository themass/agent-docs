import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { collectCandidates, extractContent } from '../../apps/extension/src/lib/content-extract'

const snapshot = JSON.parse(
  readFileSync(
    join(dirname(fileURLToPath(import.meta.url)), '../fixtures/candidates/video-feed-expected.json'),
    'utf8'
  )
) as { fixture: string; url: string; n: number; titles: string[] }

/**
 * The DOM adapter is self-contained so it can be injected verbatim; the ranking
 * logic stays pure and runs here in Node against what the real browser saw.
 */
async function report(page: import('@playwright/test').Page, path: string, n: number) {
  await page.goto(path)
  const candidates = await page.evaluate(collectCandidates)
  return extractContent(candidates, { url: new URL(path, 'http://127.0.0.1:4177').href, n })
}

test.describe('content extractor against real DOM', () => {
  test('candidate snapshot regression (video-feed)', async ({ page }) => {
    const result = await report(page, snapshot.fixture, snapshot.n)
    expect(result.items.map((item) => item.title)).toEqual(snapshot.titles)
  })

  test('video feed: carousel promo and inline activity never rank', async ({ page }) => {
    const result = await report(page, '/fixtures/video-feed.html', 4)

    expect(result.items.map((item) => item.title)).toEqual([
      '三分钟看懂扩散模型',
      '从零实现一个浏览器 Agent',
      'Rust 所有权到底在解决什么问题',
      '一次讲清 HTTP 缓存策略',
    ])
    expect(result.items.every((item) => item.url?.includes('/video/'))).toBeTruthy()
    expect(result.items[0]?.fields.duration).toBe('12:04')
    expect(result.items[0]?.fields.views).toBe('18.6万')
    expect(result.items[0]?.fields.author).toBe('AI 研究所')
    expect(result.shortfall).toBeUndefined()
  })

  test('video feed: shortfall is reported instead of padded', async ({ page }) => {
    const result = await report(page, '/fixtures/video-feed.html', 12)
    expect(result.found).toBe(5)
    expect(result.shortfall).toContain('only 5 of 12')
  })

  test('movie list: title wins over year and rating', async ({ page }) => {
    const result = await report(page, '/fixtures/movie-list.html', 4)
    expect(result.items.map((item) => item.title)).toEqual([
      '星际穿越',
      '三体 第二季',
      '沙丘',
      '奥本海默',
    ])
    expect(result.items[0]?.fields.rating).toBe('9.4')
    expect(result.items[1]?.fields.episode).toBe('更新至第12集')
  })

  test('shop grid: price and shop are read without class-name knowledge', async ({ page }) => {
    const result = await report(page, '/fixtures/shop-grid.html', 3)
    expect(result.items[0]?.title).toBe('机械键盘 87 键 客制化 热插拔')
    expect(result.items[0]?.fields.price).toBe('¥399.00')
    expect(result.items[0]?.fields.author).toBe('极客数码旗舰店')
    expect(result.items).toHaveLength(3)
  })

  test('news list: headline, source and relative date', async ({ page }) => {
    const result = await report(page, '/fixtures/news-list.html', 4)
    expect(result.items[0]?.title).toBe('某国宣布下调基准利率 25 个基点')
    expect(result.items[0]?.fields.date).toBe('2小时前')
    expect(result.items[0]?.fields.author).toBe('财经日报')
    expect(result.items[2]?.fields.date).toBe('2026-08-10')
  })

  test('every page induces its own record group without site knowledge', async ({ page }) => {
    for (const path of [
      '/fixtures/video-feed.html',
      '/fixtures/movie-list.html',
      '/fixtures/shop-grid.html',
      '/fixtures/news-list.html',
    ]) {
      const result = await report(page, path, 3)
      expect(result.strategy, path).toBe('induced')
      expect(result.items.length, path).toBe(3)
      expect(result.items.every((item) => item.confidence >= 0.7)).toBeTruthy()
    }
  })

  test('lazy feed: scrolling exposes off-screen records', async ({ page }) => {
    await page.goto('/fixtures/lazy-feed.html')
    const url = 'http://127.0.0.1:4177/fixtures/lazy-feed.html'
    const before = extractContent(await page.evaluate(collectCandidates), { url, n: 6, visibleOnly: true })
    expect(before.found).toBeLessThan(6)
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
    const after = extractContent(await page.evaluate(collectCandidates), { url, n: 6, visibleOnly: false })
    expect(after.items.map((item) => item.title)).toEqual([
      '懒加载条目一',
      '懒加载条目二',
      '懒加载条目三',
      '懒加载条目四',
      '懒加载条目五',
      '懒加载条目六',
    ])
  })

  test('shadow feed: open shadow roots are indexed', async ({ page }) => {
    const result = await report(page, '/fixtures/shadow-feed.html', 4)
    expect(result.items.map((item) => item.title)).toEqual([
      'Shadow 视频一',
      'Shadow 视频二',
      'Shadow 视频三',
      'Shadow 视频四',
    ])
  })

  test('iframe feed: inner document exposes feed links', async ({ page }) => {
    await page.goto('/fixtures/iframe-feed.html')
    await page.waitForLoadState('networkidle')
    const titles = await page.evaluate(() => {
      const frame = document.querySelector('iframe')
      const links = [...(frame?.contentDocument?.querySelectorAll('a[href]') ?? [])]
      return links.map((link) => (link.textContent ?? '').replace(/\s+/g, ' ').trim())
    })
    expect(titles).toEqual([
      'Iframe 视频一',
      'Iframe 视频二',
      'Iframe 视频三',
      'Iframe 视频四',
    ])
  })

  test('mixed layout: profile.record scopes extraction to the feed', async ({ page }) => {
    await page.goto('/fixtures/mixed-layout.html')
    const url = 'http://127.0.0.1:4177/fixtures/mixed-layout.html'
    const candidates = await page.evaluate(collectCandidates)
    const scoped = extractContent(candidates, {
      url,
      n: 4,
      profiles: [{ id: 'mixed', host: ['127.0.0.1'], record: '.feed .card', source: 'user' }],
    })
    expect(scoped.items.map((item) => item.title)).toEqual([
      '主内容一',
      '主内容二',
      '主内容三',
      '主内容四',
    ])
  })

  test('induction exposes recordPath for profile learning', async ({ page }) => {
    await page.goto('/fixtures/video-feed.html')
    const candidates = await page.evaluate(collectCandidates)
    const result = extractContent(candidates, { url: 'https://video.example.com/', n: 4 })
    expect(result.strategy).toBe('induced')
    expect(result.recordPath).toContain('card')
  })
})
