import type { MediaHint } from '@naviforge/media-plane'

import {
  collectMediaFeedTitlesFromParts,
  isLikelyVideoEntryTitle,
  isSiteNavChromeTitle,
  parseIndexedSnapshotLines,
  parseLegacySnapshotItems,
  type SnapshotParts,
} from './snapshot-media.js'

export type PageListItem = {
  index?: number
  title: string
  pageUrl?: string
  mediaUrls: string[]
}

export {
  collectMediaFeedTitlesFromParts,
  isLikelyVideoEntryTitle,
  isSiteNavChromeTitle,
  isTopicBucketSnapshotTitle,
  parseIndexedSnapshotLines,
  parseLegacySnapshotItems,
} from './snapshot-media.js'

/** @deprecated use parseIndexedSnapshotLines — kept for callers expecting old name */
export function parseSnapshotItems(content: string): Array<{ index: number; title: string }> {
  const legacy = parseLegacySnapshotItems(content)
  if (legacy.length) return legacy
  return parseIndexedSnapshotLines(content)
}

function snapshotPartsFromStrings(opts: {
  snapshotContent: string
  snapshotHeader?: string
  snapshotFooter?: string
}): SnapshotParts {
  return {
    header: opts.snapshotHeader,
    content: opts.snapshotContent,
    footer: opts.snapshotFooter,
  }
}

function mergePageItems(primary: PageListItem[], extra: PageListItem[], pageUrl?: string): PageListItem[] {
  const out: PageListItem[] = []
  const seen = new Set<string>()
  for (const item of [...primary, ...extra]) {
    if (isSiteNavChromeTitle(item.title, pageUrl ?? item.pageUrl)) continue
    const key = (item.pageUrl ?? item.title).slice(0, 96)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(item)
    if (out.length >= 48) break
  }
  return out
}

/** Heuristic merge of snapshot list + network media hints (+ optional JSON body previews). */
export function extractPageList(opts: {
  snapshotContent: string
  snapshotHeader?: string
  snapshotFooter?: string
  pageUrl?: string
  frames?: string
  mediaHints?: MediaHint[]
  jsonPreviews?: Array<{ url: string; preview: string }>
}): PageListItem[] {
  const parts = snapshotPartsFromStrings(opts)
  const blob = [parts.header, parts.content, parts.footer].filter(Boolean).join('\n')
  const mediaUrls = (opts.mediaHints ?? []).map((hint) => hint.url)

  const fromJson: PageListItem[] = []
  for (const body of opts.jsonPreviews ?? []) {
    try {
      const data = JSON.parse(body.preview) as unknown
      const list = findArrays(data)
      for (const entry of list.slice(0, 24)) {
        if (typeof entry !== 'object' || entry === null) continue
        const record = entry as Record<string, unknown>
        const title = str(record.title ?? record.name ?? record.text)
        const pageUrl = str(record.url ?? record.link ?? record.href)
        if (title) fromJson.push({ title, pageUrl, mediaUrls: [] })
      }
    } catch {
      /* skip invalid json */
    }
  }

  if (fromJson.length) return attachMedia(fromJson, mediaUrls)

  const legacy = parseLegacySnapshotItems(blob)
  const indexed = parseIndexedSnapshotLines(blob)
  const mediaTitles = collectMediaFeedTitlesFromParts(parts, 32)

  const fromSnapshot: PageListItem[] = []
  for (const item of legacy) {
    fromSnapshot.push({ index: item.index, title: item.title, mediaUrls: [] })
  }
  for (const item of indexed) {
    if (isLikelyVideoEntryTitle(item.title)) {
      fromSnapshot.push({ index: item.index, title: item.title.replace(/<[^>]*>/g, ' ').trim(), mediaUrls: [] })
    }
  }
  for (const title of mediaTitles) {
    fromSnapshot.push({ title, mediaUrls: [] })
  }

  const frameBlob = opts.frames ?? ''
  if (frameBlob) {
    for (const item of parseIndexedSnapshotLines(frameBlob, 24)) {
      if (isLikelyVideoEntryTitle(item.title)) {
        fromSnapshot.push({ index: item.index, title: item.title, mediaUrls: [] })
      }
    }
  }

  const merged = mergePageItems(fromSnapshot, [], opts.pageUrl)

  if (!merged.length) {
    return mediaUrls.length ? [{ title: '(media only)', mediaUrls }] : []
  }

  return attachMedia(merged, mediaUrls)
}

function str(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined
}

function findArrays(value: unknown): unknown[] {
  if (Array.isArray(value)) return value
  if (typeof value === 'object' && value !== null) {
    for (const child of Object.values(value)) {
      const found = findArrays(child)
      if (found.length) return found
    }
  }
  return []
}

function attachMedia(items: PageListItem[], mediaUrls: string[]): PageListItem[] {
  if (!mediaUrls.length) return items
  return items.map((item, index) => ({
    ...item,
    mediaUrls: index === 0 ? mediaUrls : item.mediaUrls,
  }))
}
