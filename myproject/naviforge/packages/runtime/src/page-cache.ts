import { urlsMatchForReuse } from './task-classifier.js'

export type PageVisit = {
  urlKey: string
  revision?: number
  visitedAt: number
}

/** Stable URL key for dedupe (origin + pathname, no query). */
export function pageUrlKey(url: string): string {
  try {
    const parsed = new URL(url)
    return `${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
  } catch {
    return url.replace(/\/$/, '')
  }
}

export function tabsOpenDedupeKey(url: string): string {
  return `tabs_open|${pageUrlKey(url)}`
}

export function recordPageVisit(
  visits: Map<string, PageVisit>,
  url: string,
  revision?: number
): void {
  const key = pageUrlKey(url)
  if (!key) return
  visits.set(key, { urlKey: key, revision, visitedAt: Date.now() })
}

export function pageAlreadyVisited(
  visits: Map<string, PageVisit>,
  url: string,
  revision?: number
): boolean {
  const key = pageUrlKey(url)
  const hit = visits.get(key)
  if (!hit) return false
  if (revision == null || hit.revision == null) return true
  return hit.revision === revision
}

export function isRedundantTabsOpen(
  visits: Map<string, PageVisit>,
  targetUrl: string,
  currentUrl: string
): boolean {
  const target = pageUrlKey(targetUrl)
  if (!target) return false
  if (urlsMatchForReuse(targetUrl, currentUrl)) return true
  return visits.has(target)
}
