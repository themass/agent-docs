import type { DomPlane } from '@naviforge/dom-plane'

import type { CatalogCrawlPlan, CatalogDiscoverResult, CatalogSection } from './types.js'

/**
 * Site-agnostic catalog discovery (runs in page MAIN world via dom_execute_js).
 * Finds nav sections, pagination, and dominant list-item URL shape by voting —
 * no host names, no vertical-specific selectors.
 */
export const CATALOG_DISCOVER_JS = `(() => {
  const origin = location.origin
  const clean = (s) => (s || '').trim().replace(/\\s+/g, ' ')
  const links = [...document.querySelectorAll('a[href]')].map((a) => ({
    t: clean(a.textContent),
    h: a.href,
    inNav: Boolean(
      a.closest(
        'header,nav,[role=navigation],[role=tablist],.tabs,.tab,.categories,.menu,[class*="category"],[class*="nav"]'
      )
    ),
    inMain: Boolean(
      a.closest('main,[role=main],article,.content,#content,.list,.grid,.feed,.products,.posts')
    ),
  }))

  const skipLabel = /^(home|index|首页|login|登录|register|注册|sign\\s*in|sign\\s*up|search|搜索|cart|购物车|more|更多|menu|help|关于|about)$/i

  function shape(href) {
    try {
      const u = new URL(href, location.href)
      if (u.origin !== origin) return ''
      const parts = u.pathname.split('/').filter(Boolean)
      if (parts.length < 2) return ''
      return parts
        .map((seg, i, arr) =>
          i === arr.length - 1 && seg.length >= 3 && /[0-9A-Za-z]{3,}/.test(seg) ? '*' : seg
        )
        .join('/')
    } catch {
      return ''
    }
  }

  const shapeCounts = new Map()
  for (const x of links) {
    if (!x.h.startsWith(origin)) continue
    if (!x.inMain) continue
    const s = shape(x.h)
    if (!s || s.split('/').length < 2) continue
    shapeCounts.set(s, (shapeCounts.get(s) || 0) + 1)
  }
  const detailShape =
    [...shapeCounts.entries()].sort((a, b) => b[1] - a[1]).find(([, n]) => n >= 3)?.[0] ?? undefined

  const sections = []
  const seen = new Set()
  for (const x of links) {
    if (!x.h.startsWith(origin)) continue
    if (!x.inNav) continue
    if (!x.t || x.t.length > 28 || x.t.length < 2) continue
    if (skipLabel.test(x.t)) continue
    if (seen.has(x.h)) continue
    seen.add(x.h)
    sections.push({ name: x.t, url: x.h })
  }

  const pagination = links
    .filter(
      (x) =>
        x.h.startsWith(origin) &&
        /^(\\d+|next|prev|上一页|下一页|›|»|‹|‹)$/i.test(x.t)
    )
    .slice(0, 20)
    .map((x) => ({ label: x.t, url: x.h }))
  const relNext = document.querySelector('a[rel="next"],link[rel="next"]')
  if (relNext && relNext.href && relNext.href.startsWith(origin)) {
    pagination.push({ label: 'rel=next', url: relNext.href })
  }

  const infiniteScroll = Boolean(
    document.querySelector(
      '.infinite-scroll,[data-infinite],[class*="infinite"],.load-more,button[class*="load-more"]'
    )
  )

  const listSample = links
    .filter((x) => {
      if (!x.h.startsWith(origin)) return false
      if (detailShape) return shape(x.h) === detailShape
      return x.inMain && x.t.length >= 2
    })
    .slice(0, 16)
    .map((x) => ({ title: x.t.slice(0, 160), url: x.h }))

  return {
    url: location.href,
    origin,
    sections: sections.slice(0, 32),
    pagination,
    detailShape,
    listSample,
    infiniteScroll,
  }
})()`

export const CATALOG_PAGE_URL_JS = (pageNum: number) => `(() => {
  const origin = location.origin
  const want = ${pageNum}
  const clean = (s) => (s || '').trim()
  const links = [...document.querySelectorAll('a[href]')].filter((a) => a.href.startsWith(origin))
  const exact = links.find((a) => clean(a.textContent) === String(want))
  if (exact) return exact.href
  if (want <= 2) {
    const next = links.find((a) => /^(下一页|next|›|»)$/i.test(clean(a.textContent)))
    if (next) return next.href
  }
  return null
})()`

export function parseDiscoverPayload(raw: unknown): CatalogDiscoverResult | null {
  if (!raw || typeof raw !== 'object') return null
  const rec = raw as Record<string, unknown>
  const origin = typeof rec.origin === 'string' ? rec.origin : ''
  const url = typeof rec.url === 'string' ? rec.url : ''
  if (!origin || !url) return null

  const sections: CatalogSection[] = []
  if (Array.isArray(rec.sections)) {
    for (const item of rec.sections) {
      if (!item || typeof item !== 'object') continue
      const row = item as Record<string, unknown>
      const name = typeof row.name === 'string' ? row.name : typeof row.text === 'string' ? row.text : ''
      const href = typeof row.url === 'string' ? row.url : typeof row.href === 'string' ? row.href : ''
      if (name && href) sections.push({ name, url: href })
    }
  }

  const pagination: CatalogDiscoverResult['pagination'] = []
  if (Array.isArray(rec.pagination)) {
    for (const item of rec.pagination) {
      if (!item || typeof item !== 'object') continue
      const row = item as Record<string, unknown>
      const label = typeof row.label === 'string' ? row.label : typeof row.t === 'string' ? row.t : ''
      const href = typeof row.url === 'string' ? row.url : typeof row.h === 'string' ? row.h : ''
      if (label && href) pagination.push({ label, url: href })
    }
  }

  const listSample: CatalogDiscoverResult['listSample'] = []
  if (Array.isArray(rec.listSample)) {
    for (const item of rec.listSample) {
      if (!item || typeof item !== 'object') continue
      const row = item as Record<string, unknown>
      const title = typeof row.title === 'string' ? row.title : typeof row.t === 'string' ? row.t : ''
      const href = typeof row.url === 'string' ? row.url : typeof row.h === 'string' ? row.h : ''
      if (title && href) listSample.push({ title, url: href })
    }
  }

  return {
    url,
    origin,
    sections,
    pagination,
    detailShape: typeof rec.detailShape === 'string' ? rec.detailShape : undefined,
    listSample,
    infiniteScroll: Boolean(rec.infiniteScroll),
  }
}

export async function discoverCatalogPage(dom: DomPlane): Promise<CatalogDiscoverResult | null> {
  if (!dom.executeJs) return null
  const discovered = await dom.executeJs({ code: CATALOG_DISCOVER_JS })
  if (!discovered.ok) return null
  return parseDiscoverPayload((discovered.data as { result?: unknown }).result)
}

/** Single-section plan anchored on the current URL (no nav-section expansion). */
export function buildCurrentPagePlan(
  discover: CatalogDiscoverResult,
  spec: { pagesPerSection: number; wantsMediaUrl: boolean }
): CatalogCrawlPlan {
  return {
    startUrl: discover.url,
    sections: [{ name: '(current)', url: discover.url }],
    detailShape: discover.detailShape,
    pagesPerSection: spec.pagesPerSection,
    wantsMediaUrl: spec.wantsMediaUrl,
    infiniteScroll: discover.infiniteScroll,
  }
}

export function buildCatalogPlan(
  discover: CatalogDiscoverResult,
  spec: { pagesPerSection: number; maxSections: number; wantsMediaUrl: boolean }
): { plan: CatalogCrawlPlan; usedFallbackSection: boolean } {
  let sections = discover.sections.slice(0, spec.maxSections)
  let usedFallbackSection = false
  if (!sections.length) {
    sections = [{ name: '(current)', url: discover.url }]
    usedFallbackSection = true
  }
  return {
    usedFallbackSection,
    plan: {
      startUrl: discover.url,
      sections,
      detailShape: discover.detailShape,
      pagesPerSection: spec.pagesPerSection,
      wantsMediaUrl: spec.wantsMediaUrl,
      infiniteScroll: discover.infiniteScroll,
    },
  }
}
