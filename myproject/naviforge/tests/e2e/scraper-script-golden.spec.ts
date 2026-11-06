import { expect, test } from '@playwright/test'

import { CATALOG_DISCOVER_JS, parseDiscoverPayload } from '../../packages/runtime/src/catalog-crawl/discover.js'
import { resolveDeliverable } from '../../packages/runtime/src/deliverable.js'
import { resolveTaskIntent } from '../../packages/runtime/src/task-intent.js'

/**
 * Golden acceptance G3–G5 from SCRAPER_AGENT_RELIABILITY_PLAN.md §10.1.
 * G1/G2 live in golden-browser-agent.spec.ts; G1 人工录屏仍需人工存档。
 */

test.describe('scraper golden — G3/G4/G5', () => {
  test('G3: 每个分类前 2 页 JSON → multi_hop_crawl (no script)', () => {
    const task = '每个分类前 2 页，JSON 输出'
    expect(resolveTaskIntent(task)).toBe('multi_hop_crawl')
    expect(resolveDeliverable(task)).toBe('data')
  })

  test('G4: 总结当前页 → page_read / summary', () => {
    const task = '总结当前页'
    expect(resolveTaskIntent(task)).toBe('page_read')
    expect(resolveDeliverable(task)).toBe('summary')
  })

  test('G5: SPA catalog fixture discover ≥ 3 sections', async ({ page }) => {
    await page.goto('/fixtures/spa-catalog.html')
    const raw = await page.evaluate((code) => {
      // Discover script is an IIFE string shared with the runtime plane.
      return (0, eval)(code) as unknown
    }, CATALOG_DISCOVER_JS)
    const discover = parseDiscoverPayload(raw)
    expect(discover).toBeTruthy()
    expect(discover!.sections.length).toBeGreaterThanOrEqual(3)

    const scriptTask =
      '分析这个网站的商品分类列表，给我生成一个 python 脚本，抓取每个分类下的第一页。页码默认值为1'
    expect(resolveTaskIntent(scriptTask)).toBe('script_authoring')
    expect(resolveDeliverable(scriptTask)).toBe('script')
  })
})
