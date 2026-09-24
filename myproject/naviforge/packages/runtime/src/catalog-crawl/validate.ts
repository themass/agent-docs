import type { CatalogCrawlResult, CatalogValidationReport } from './types.js'
import { entryHasPlayableEvidence } from './media-entry.js'

function normalizeEntryUrl(url: string | undefined): string {
  if (!url) return ''
  try {
    const u = new URL(url)
    u.hash = ''
    return u.href
  } catch {
    return url.trim()
  }
}

/** Phase 5: dedupe, required-field gaps, light sampling summary. */
export function validateCatalogCrawlResult(
  result: CatalogCrawlResult,
  opts: { wantsMediaUrl: boolean }
): CatalogValidationReport {
  const seen = new Set<string>()
  let totalEntries = 0
  let duplicatesRemoved = 0
  let missingMedia = 0
  let embedOnly = 0
  const issues: string[] = []

  for (const block of result.sections) {
    for (const page of block.pages) {
      const kept: typeof page.entries = []
      for (const entry of page.entries) {
        totalEntries++
        const key = normalizeEntryUrl(entry.url) || `title:${entry.title}`
        if (seen.has(key)) {
          duplicatesRemoved++
          continue
        }
        seen.add(key)
        if (opts.wantsMediaUrl && entry.url) {
          if (!entryHasPlayableEvidence(entry)) missingMedia++
          else if (!entry.mediaUrl && entry.playPageUrl) embedOnly++
        }
        kept.push(entry)
      }
      page.entries = kept
    }
  }

  const uniqueEntries = totalEntries - duplicatesRemoved
  if (duplicatesRemoved > 0) {
    issues.push(`removed ${duplicatesRemoved} duplicate entries`)
  }
  if (opts.wantsMediaUrl && missingMedia > 0) {
    issues.push(`${missingMedia} entries with no mediaUrl or playPageUrl`)
  }
  if (opts.wantsMediaUrl && embedOnly > 0) {
    issues.push(`${embedOnly} embed-only entries (agent: click play / spawn / network_read)`)
  }
  if (!result.complete) {
    issues.push(result.truncatedReason ?? 'crawl incomplete')
  }

  const sampledOk = Math.min(2, uniqueEntries)
  return {
    totalEntries,
    uniqueEntries,
    duplicatesRemoved,
    missingMedia,
    embedOnly,
    sampledOk,
    issues,
  }
}
