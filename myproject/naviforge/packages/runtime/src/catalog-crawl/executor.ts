import type { AgentCtx } from '../agent-ctx.js'
import type { DomPlane } from '@naviforge/dom-plane'
import type { DomContentItem } from '@naviforge/dom-plane'
import { AUTH_GATE_JS, parseAuthGatePayload } from './auth-gate.js'
import {
  buildCatalogPlan,
  CATALOG_DISCOVER_JS,
  CATALOG_PAGE_URL_JS,
  parseDiscoverPayload,
} from './discover.js'
import { detailShapeRegex } from './page-role.js'
import { resolveMediaWithHops } from './multihop.js'
import { CATALOG_TABLE_EXTRACT_JS, parseTableExtractPayload } from './table-extract.js'
import { throttleCatalogNav } from './throttle.js'
import type { CatalogCrawlResult, CatalogCrawlSpec, CatalogListEntry, CatalogPageSlice } from './types.js'
import { validateCatalogCrawlResult } from './validate.js'

function toEntries(items: DomContentItem[], detailRe?: RegExp): CatalogListEntry[] {
  const out: CatalogListEntry[] = []
  const seen = new Set<string>()
  for (const item of items) {
    if (!item.title?.trim()) continue
    if (item.url && detailRe) {
      try {
        if (!detailRe.test(new URL(item.url).pathname)) continue
      } catch {
        continue
      }
    }
    const key = item.url ?? item.title
    if (seen.has(key)) continue
    seen.add(key)
    out.push({
      title: item.title,
      url: item.url,
      fields: item.fields,
    })
  }
  return out
}

async function resolvePageUrl(
  dom: DomPlane,
  sectionUrl: string,
  pageIndex: number
): Promise<string | null> {
  if (pageIndex === 0) return sectionUrl
  if (!dom.executeJs) return null
  const pageNum = pageIndex + 1
  const ran = await dom.executeJs({ code: CATALOG_PAGE_URL_JS(pageNum) })
  if (!ran.ok) return null
  const href = (ran.data as { result?: unknown }).result
  return typeof href === 'string' && href.startsWith('http') ? href : null
}

async function extractTablePage(dom: DomPlane, pageUrl: string): Promise<CatalogPageSlice | null> {
  if (!dom.executeJs) return null
  const ran = await dom.executeJs({ code: CATALOG_TABLE_EXTRACT_JS })
  if (!ran.ok) return null
  const entries = parseTableExtractPayload((ran.data as { result?: unknown }).result)
  return { url: pageUrl, entries }
}

async function extractListPage(
  dom: DomPlane,
  pageUrl: string,
  detailRe: RegExp | undefined,
  maxItems: number,
  wantsTableRows: boolean
): Promise<CatalogPageSlice | null> {
  if (wantsTableRows) {
    const tableSlice = await extractTablePage(dom, pageUrl)
    if (tableSlice && tableSlice.entries.length > 0) return tableSlice
  }
  if (!dom.extractContent) return null
  const listed = await dom.extractContent(maxItems)
  if (!listed.ok) return null
  return {
    url: pageUrl,
    entries: toEntries(listed.data.items, detailRe),
    shortfall: listed.data.shortfall,
  }
}

async function checkPageBlocked(dom: DomPlane): Promise<boolean> {
  if (!dom.executeJs) return false
  const ran = await dom.executeJs({ code: AUTH_GATE_JS })
  if (!ran.ok) return false
  const gate = parseAuthGatePayload((ran.data as { result?: unknown }).result)
  if (!gate) return false
  return gate.needsAuth || gate.captcha
}

/** Deterministic multi-section listing crawl — vertical-agnostic. */
export async function runCatalogCrawl(
  ctx: AgentCtx,
  spec: CatalogCrawlSpec
): Promise<CatalogCrawlResult | null> {
  const dom = ctx.agent.planes.dom
  if (!dom.executeJs || !dom.navigate || !dom.extractContent) return null

  if (await checkPageBlocked(dom)) {
    return {
      plan: {
        startUrl: '',
        sections: [],
        pagesPerSection: spec.pagesPerSection,
        wantsMediaUrl: spec.wantsMediaUrl,
      },
      sections: [],
      complete: false,
      authBlocked: true,
      truncatedReason:
        'page friction (login/captcha/rate-limit) — complete Phase 0 via page-friction / system_captcha_wait',
    }
  }

  const discovered = await dom.executeJs({ code: CATALOG_DISCOVER_JS })
  if (!discovered.ok) return null
  const payload = parseDiscoverPayload((discovered.data as { result?: unknown }).result)
  if (!payload) return null

  const { plan } = buildCatalogPlan(payload, spec)
  const detailRe = detailShapeRegex(plan.detailShape)
  const result: CatalogCrawlResult = {
    plan,
    sections: [],
    complete: true,
  }

  let mediaBudget = spec.maxMediaFetches

  for (const section of plan.sections) {
    const sectionResult: CatalogCrawlResult['sections'][number] = {
      section,
      pages: [],
    }
    try {
      for (let pageIndex = 0; pageIndex < plan.pagesPerSection; pageIndex++) {
        const pageUrl = await resolvePageUrl(dom, section.url, pageIndex)
        if (!pageUrl) {
          if (pageIndex > 0) break
          result.complete = false
          result.truncatedReason = `pagination missing for ${section.name} page ${pageIndex + 1}`
          break
        }
        await throttleCatalogNav()
        const nav = await dom.navigate('url', pageUrl)
        if (!nav.ok) {
          sectionResult.error = nav.error.message
          result.complete = false
          break
        }
        if (dom.wait) await dom.wait({ kind: 'stable', timeoutMs: 700 })

        const slice = await extractListPage(
          dom,
          pageUrl,
          detailRe,
          spec.maxItemsPerPage,
          spec.wantsTableRows
        )
        if (!slice) {
          sectionResult.error = 'list extract failed'
          result.complete = false
          break
        }
        slice.url = pageUrl

        if (spec.wantsMediaUrl && mediaBudget > 0) {
          for (const entry of slice.entries) {
            if (!entry.url || mediaBudget <= 0) break
            const resolved = await resolveMediaWithHops(
              ctx,
              dom,
              entry.url,
              spec.maxDetailHops
            )
            if (resolved.mediaUrl) entry.mediaUrl = resolved.mediaUrl
            if (resolved.playPageUrl) entry.playPageUrl = resolved.playPageUrl
            if (resolved.format) entry.format = resolved.format
            if (resolved.confidence != null) entry.confidence = resolved.confidence
            if (resolved.shortfall) entry.shortfall = resolved.shortfall
            mediaBudget--
          }
        }

        sectionResult.pages.push(slice)
      }
    } catch (e) {
      sectionResult.error = (e as Error).message
      result.complete = false
    }
    result.sections.push(sectionResult)
  }

  result.validation = validateCatalogCrawlResult(result, { wantsMediaUrl: spec.wantsMediaUrl })
  if (result.authBlocked) result.complete = false

  return result
}
