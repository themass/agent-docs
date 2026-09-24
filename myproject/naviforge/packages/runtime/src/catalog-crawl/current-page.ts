import type { AgentCtx } from '../agent-ctx.js'
import type { DomPlane } from '@naviforge/dom-plane'
import type { DomContentItem } from '@naviforge/dom-plane'

import { AUTH_GATE_JS, parseAuthGatePayload } from './auth-gate.js'
import { buildCurrentPagePlan } from './discover.js'
import { detailShapeRegex } from './page-role.js'
import { resolveMediaWithHops } from './multihop.js'
import { CATALOG_TABLE_EXTRACT_JS, parseTableExtractPayload } from './table-extract.js'
import type {
  CatalogCrawlResult,
  CatalogCrawlSpec,
  CatalogDiscoverResult,
  CatalogListEntry,
  CatalogPageSlice,
} from './types.js'
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

/**
 * Extract the current tab only — no section navigation, no pagination hops.
 * Media resolution runs only for a single-item list when resolveMedia=true.
 */
export async function runCurrentPageListCrawl(
  ctx: AgentCtx,
  spec: CatalogCrawlSpec,
  discover: CatalogDiscoverResult,
  opts?: { resolveMedia?: boolean }
): Promise<CatalogCrawlResult | null> {
  const dom = ctx.agent.planes.dom
  if (!dom.extractContent) return null

  if (await checkPageBlocked(dom)) {
    return {
      plan: buildCurrentPagePlan(discover, spec),
      sections: [],
      complete: false,
      authBlocked: true,
      truncatedReason:
        'page friction (login/captcha/rate-limit) — complete Phase 0 via page-friction / system_captcha_wait',
    }
  }

  const plan = buildCurrentPagePlan(discover, spec)
  const detailRe = detailShapeRegex(plan.detailShape)
  const slice = await extractListPage(
    dom,
    discover.url,
    detailRe,
    spec.maxItemsPerPage,
    spec.wantsTableRows
  )

  if (!slice) {
    return {
      plan,
      sections: [{ section: plan.sections[0]!, pages: [], error: 'list extract failed' }],
      complete: false,
      truncatedReason: 'current-page list extract failed',
    }
  }

  const resolveMedia = Boolean(opts?.resolveMedia && spec.wantsMediaUrl)
  if (resolveMedia && slice.entries.length === 1 && slice.entries[0]?.url) {
    const entry = slice.entries[0]!
    const resolved = await resolveMediaWithHops(ctx, dom, entry.url!, spec.maxDetailHops)
    if (resolved.mediaUrl) entry.mediaUrl = resolved.mediaUrl
    if (resolved.playPageUrl) entry.playPageUrl = resolved.playPageUrl
    if (resolved.format) entry.format = resolved.format
    if (resolved.confidence != null) entry.confidence = resolved.confidence
    if (resolved.shortfall) entry.shortfall = resolved.shortfall
  } else if (spec.wantsMediaUrl && slice.entries.length > 1) {
    slice.shortfall =
      slice.shortfall ??
      `${slice.entries.length} list items — media URLs require spawn (not resolved in preflight)`
  }

  const result: CatalogCrawlResult = {
    plan,
    sections: [{ section: plan.sections[0]!, pages: [slice] }],
    complete: true,
  }
  result.validation = validateCatalogCrawlResult(result, { wantsMediaUrl: spec.wantsMediaUrl })
  return result
}
