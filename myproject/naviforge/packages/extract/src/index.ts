import type { MediaHint } from '@naviforge/media-plane'

export type PageListItem = {
  index?: number
  title: string
  pageUrl?: string
  mediaUrls: string[]
}

const LINE_ITEM = /^\[(\d+)\]\s+(\w+)(?:\s+"([^"]*)")?/

/** Parse indexed snapshot lines into list items. */
export function parseSnapshotItems(content: string): Array<{ index: number; title: string }> {
  const items: Array<{ index: number; title: string }> = []
  for (const line of content.split('\n')) {
    const match = LINE_ITEM.exec(line.trim())
    if (!match) continue
    const title = match[3]?.trim() || match[2]
    if (!title || /button|nav|menu|logo/i.test(title) && title.length < 4) continue
    items.push({ index: Number(match[1]), title })
  }
  return items.slice(0, 48)
}

/** Heuristic merge of DOM list + network media hints (+ optional JSON body previews). */
export function extractPageList(opts: {
  snapshotContent: string
  frames?: string
  mediaHints?: MediaHint[]
  jsonPreviews?: Array<{ url: string; preview: string }>
}): PageListItem[] {
  const domItems = parseSnapshotItems(opts.snapshotContent)
  const frameItems = opts.frames ? parseSnapshotItems(opts.frames) : []
  const merged = [...domItems, ...frameItems]
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

  if (!merged.length) {
    return mediaUrls.length
      ? [{ title: '(media only)', mediaUrls }]
      : []
  }

  return attachMedia(
    merged.map((item) => ({ index: item.index, title: item.title, mediaUrls: [] as string[] })),
    mediaUrls
  )
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
