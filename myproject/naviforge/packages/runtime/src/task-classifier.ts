import type { ThreadReuse } from '@naviforge/session'

import { isCatalogCrawlTask, isSiteCatalogSopTask, parseCatalogCrawlSpec } from './catalog-crawl/spec.js'
import { MEDIA_AGENT_JUDGMENT_GUIDANCE, MEDIA_ENTRY_OUTPUT_SCHEMA } from './catalog-crawl/media-entry.js'
import { resolveDeliverable, shouldEmitSiteCatalogGuidance } from './deliverable.js'

export type TaskMode = 'in_page' | 'research' | 'general' | 'list_detail'

const RESEARCH =
  /同类型|同类|类似项目|竞品|alternatives?|similar (?:to|projects?)|github|gitlab|gitee|两个.{0,12}(项目|仓库|库|repo)|对比|区别|difference|compare|vs\.?|差异/i

/** Off-page research: web_search → open sources → compare. */
export function isResearchTask(task: string): boolean {
  return RESEARCH.test(task.trim())
}

/** Knowledge-style ask without DOM ops on the current shell page. */
export function isGeneralTask(task: string): boolean {
  const t = task.trim()
  if (isResearchTask(t) || isPageReadTask(t) || shouldHintListThenDetail(t) || requestedList(t)) return false
  if (/当前页|本页|this page|dom_|点击|提取|top\s*\d+|前\s*\d+|标记|高亮/i.test(t)) return false
  return /[?？]|什么是|为什么|怎么|如何|what|why|how/i.test(t) && t.length <= 240
}

/** Many static document URLs (e.g. repo tree listing) — prefer fetch_text batches in spawn briefs. */
export function isBulkMdCatalogTask(task: string): boolean {
  const t = task.trim()
  if (!/github\.com\/[^/\s]+\/[^/\s]+\/tree\//i.test(t)) return false
  return /整理|分类|去重|所有|全部|每个|不要丢失|catalog|dedupe|list all/i.test(t)
}

export { isCatalogCrawlTask, isSiteCatalogSopTask, parseCatalogCrawlSpec }

export function resolveTaskMode(task: string): TaskMode {
  if (shouldHintListThenDetail(task)) return 'list_detail'
  if (isResearchTask(task)) return 'research'
  if (isGeneralTask(task)) return 'general'
  return 'in_page'
}

/** 「读当前页」：总结 / 介绍 / 是什么 / 干什么 — not list→detail or web search. */
export function isPageReadTask(task: string): boolean {
  const t = task.trim()
  if (/(第\s*[0-9一二三四五六七八九十]+个|top\s*\d+)/i.test(t)) return false
  if (RESEARCH.test(t)) return false
  if (
    /总结.{0,16}(页面|当前|这篇|本页|文档)|概括.{0,16}(页面|当前|这篇|本页)|页面.{0,8}(总结|概括)/.test(
      t
    )
  ) {
    return true
  }
  return (
    /(介绍|讲讲|说说|概述|是什么|做什么|干什么|干嘛|用途|readme|项目情况)/i.test(t) &&
    /(项目|页面|当前|这篇|本页|这个|仓库|repo|网站|产品|应用)/i.test(t) &&
    !/两个|对比|区别|github/i.test(t)
  )
}

/** Open a list item only when the user named a row / story / detail page. */
export function shouldHintListThenDetail(task: string): boolean {
  if (isPageReadTask(task)) return false
  return /(第\s*[0-9一二三四五六七八九十]+个|top\s*\d+|讲了什么|什么故事|详情页)/i.test(task)
}

/** A "top N" ask, plus whether the user wanted the page marked or just the data. */
export function requestedList(task: string): { n: number; mark: boolean } | null {
  if (isCatalogCrawlTask(task)) return null
  if (/前\s*\d{1,2}\s*页|前\s*\d{1,2}\s*个?\s*page|\d{1,2}\s*pages?\s*(each|per)|每\s*页/i.test(task)) {
    return null
  }
  const topMatch = /(?:top\s*|前\s*)(\d{1,2})/i.exec(task)
  const countMatch =
    topMatch ??
    /(?:抓取|获取|找出|列出|提取)?(?:本页|当前页|页面|本网站)?\s*(\d{1,2})\s*个/i.exec(task)
  if (!countMatch) return null
  const n = Math.min(12, Math.max(1, Number(countMatch[1])))
  const refused =
    /不(?:需要|要|用)?(?:标记|高亮|框出)|不要(?:标记|高亮|框出)|无需(?:标记|高亮|框出)/i.test(task)
  const markAsk = /标记|高亮|框出|highlight|mark/i.test(task)
  const needsModel =
    /故事|简述|总结|讲了|简介|完事了|做完了|用了?\s*skill|skill\s*了|为什么|是否确认/i.test(task) &&
    !markAsk
  if (needsModel) return null
  if (markAsk && !refused) return { n, mark: true }
  const extractAsk =
    /提取|找出|列出|抓取|获取|名称|链接|标题/i.test(task) ||
    /(?:top\s*|前\s*)\d{1,2}/i.test(task)
  if (!extractAsk) return null
  return { n, mark: false }
}

export function requestedTopN(task: string): number | null {
  const request = requestedList(task)
  return request?.mark ? request.n : null
}

export function urlsMatchForReuse(a: string, b: string): boolean {
  const key = (url: string) => {
    try {
      const parsed = new URL(url)
      return `${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
    } catch {
      return url.replace(/\/$/, '')
    }
  }
  return Boolean(a && b && key(a) === key(b))
}

export function bareSkillId(id: string): string {
  const at = id.lastIndexOf('@')
  return at > 0 ? id.slice(0, at) : id
}

/** @deprecated Use isSiteCatalogSopTask — parallel fan-out is phase 3 of catalog SOP. */
export function shouldHintParallelSubtasks(task: string): boolean {
  return isSiteCatalogSopTask(task)
}

export function parallelSubtaskGuidanceNotes(task: string): string[] {
  if (resolveDeliverable(task) === 'script') return []
  if (!shouldEmitSiteCatalogGuidance(task, resolveDeliverable(task))) return []
  if (!isSiteCatalogSopTask(task)) return []
  const mediaTask = parseCatalogCrawlSpec(task).wantsMediaUrl
  const lines = [
    'GUIDANCE: 站点目录 SOP — skill_load traverse。preflight catalog-crawl 若已跑则在其结果上继续。',
    'GUIDANCE: 分页 + 详情可 spawn≤3；禁止列表页 js 空转。',
    'GUIDANCE: 会话门控 — PAGE FRICTION + skill_load friction；人机用 system_captcha_wait。',
    `GUIDANCE: ${MEDIA_ENTRY_OUTPUT_SCHEMA.replace(/\n/g, ' ')}`,
  ]
  if (mediaTask) lines.push(...MEDIA_AGENT_JUDGMENT_GUIDANCE)
  return lines
}

/** Deterministic GUIDANCE notes before the model loop (shared by TaskHintHook). */
export function taskGuidanceNotes(task: string, reuse: ThreadReuse): string[] {
  if (resolveDeliverable(task) === 'script') return []
  const mode = resolveTaskMode(task)
  if (isSiteCatalogSopTask(task)) {
    return parallelSubtaskGuidanceNotes(task)
  }
  if (isCatalogCrawlTask(task)) {
    return [
      'GUIDANCE: catalog-crawl 若 partial，继续未完成分区/分页。列表项只信同源；详情用 PAGE SIGNALS / observe；剩余条目 spawn 并行补全（每批 ≤3）。',
    ]
  }
  if (/标记|高亮|框出/.test(task)) return []
  if (mode === 'research') {
    return [
      'GUIDANCE: research: web_search → tabs open 2–3 URLs → observe read → system_done 对比；勿对壳页 snapshot 空转；可 skill_load research',
    ]
  }
  if (mode === 'general') {
    return [
      'GUIDANCE: general: answer from THREAD / CONTEXT OBSERVATION; web_search if needed; skip dom_snapshot on shell page',
    ]
  }
  if (isPageReadTask(task)) {
    return [
      'GUIDANCE: read-page: PREFLIGHT observe body then system_done（结论先行）；no list extract or scroll-hunt',
    ]
  }
  if (reuse.page) {
    return [
      'GUIDANCE: follow-up: answer from PAGE EVIDENCE / 会话上下文; do not skill_load observe again; do not loop extract',
    ]
  }
  if (mode === 'list_detail') {
    return [
      'GUIDANCE: list→detail: skill_load traverse → observe list → 打开第 k 条 → summarize → system_done',
    ]
  }
  return []
}