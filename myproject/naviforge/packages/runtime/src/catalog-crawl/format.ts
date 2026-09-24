import type { CatalogCrawlPlan, CatalogCrawlResult } from './types.js'

export function formatCatalogPlanEvidence(plan: CatalogCrawlPlan): string {
  const lines = [
    `CATALOG PLAN (${plan.startUrl})`,
    `pages/section=${plan.pagesPerSection} sections=${plan.sections.length} detailShape=${plan.detailShape ?? '(auto)'}`,
    plan.infiniteScroll ? 'pagination=infinite-scroll (use dom_scroll + re-extract)' : '',
    ...plan.sections.slice(0, 12).map((s, i) => `  ${i + 1}. ${s.name} → ${s.url}`),
  ]
  return lines.join('\n')
}

export function formatCatalogCrawlResult(result: CatalogCrawlResult): string {
  const lines: string[] = []
  lines.push(
    result.complete
      ? '目录爬取完成（通用 catalog-crawl 执行器）'
      : `目录爬取部分完成${result.truncatedReason ? `：${result.truncatedReason}` : ''}`
  )
  lines.push(`起始：${result.plan.startUrl}`)
  if (result.plan.detailShape) lines.push(`列表项 URL 形状：/${result.plan.detailShape}`)

  for (const block of result.sections) {
    lines.push(`\n## ${block.section.name}`)
    if (block.error) lines.push(`(error: ${block.error})`)
    for (const [pi, page] of block.pages.entries()) {
      lines.push(`\n### 第 ${pi + 1} 页 · ${page.url}`)
      if (page.shortfall) lines.push(`(${page.shortfall})`)
      page.entries.forEach((entry, i) => {
        const link = entry.url ? `\n   list: ${entry.url}` : ''
        const media = entry.mediaUrl
          ? `\n   media(${entry.format ?? 'stream'}): ${entry.mediaUrl}`
          : ''
        const play = entry.playPageUrl ? `\n   playPage: ${entry.playPageUrl}` : ''
        const conf =
          entry.confidence != null ? `\n   confidence: ${entry.confidence.toFixed(2)}` : ''
        const gap = entry.shortfall ? `\n   shortfall: ${entry.shortfall}` : ''
        const fields =
          entry.fields && Object.keys(entry.fields).length
            ? `\n   fields: ${JSON.stringify(entry.fields).slice(0, 200)}`
            : ''
        lines.push(`${i + 1}. ${entry.title}${link}${media}${play}${conf}${gap}${fields}`)
      })
    }
  }
  if (result.validation) {
    const v = result.validation
    lines.push(
      `\n校验：${v.uniqueEntries} 条（去重 ${v.duplicatesRemoved}）` +
        (v.missingMedia ? `，无可播放证据 ${v.missingMedia}` : '') +
        (v.embedOnly ? `，仅 embed 页 ${v.embedOnly}` : '')
    )
    if (v.issues.length) lines.push(`issues: ${v.issues.join('; ')}`)
  }
  if (result.authBlocked) {
    lines.push('\n⚠ 页面摩擦阻塞 — 请 page-friction / system_captcha_wait')
  }
  return lines.join('\n')
}
