import { formatCatalogCrawlResult } from './catalog-crawl/format.js'
import type { CatalogCrawlResult } from './catalog-crawl/types.js'
import type { CatalogStrategy } from './catalog-crawl/strategy.js'

export type PreflightEvidence = {
  strategy: CatalogStrategy
  listResult?: string
  mediaPlayback?: string
  catalogCrawl?: CatalogCrawlResult | null
  spawnGuidance?: string
}

function catalogHasEntries(crawl: CatalogCrawlResult): boolean {
  return crawl.sections.some((s) => s.pages.some((p) => p.entries.length > 0))
}

function catalogHasMedia(crawl: CatalogCrawlResult): boolean {
  return crawl.sections.some((s) =>
    s.pages.some((p) => p.entries.some((e) => e.mediaUrl || e.playPageUrl))
  )
}

/** Merge preflight evidence; catalog partial beats single-playback shortcut. */
export function synthesizePreflightResult(evidence: PreflightEvidence): string | undefined {
  const { strategy, listResult, mediaPlayback, catalogCrawl, spawnGuidance } = evidence

  if (catalogCrawl && catalogHasEntries(catalogCrawl)) {
    const body = formatCatalogCrawlResult(catalogCrawl)
    if (spawnGuidance && strategy === 'spawn-media' && !catalogHasMedia(catalogCrawl)) {
      return `${body}\n\n${spawnGuidance}`
    }
    return body
  }

  if (strategy === 'media-extract' && mediaPlayback) return mediaPlayback

  if (listResult) {
    return spawnGuidance ? `${listResult}\n\n${spawnGuidance}` : listResult
  }

  if (mediaPlayback && strategy !== 'spawn-media' && strategy !== 'current-page-list') {
    return mediaPlayback
  }

  return undefined
}
