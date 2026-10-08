import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'
import {
  extractPageList,
  isLikelyVideoEntryTitle,
  isSiteNavChromeTitle,
  type PageListItem,
} from '@naviforge/extract'
import { mediaHintsFromUrls, type MediaHint } from '@naviforge/media-plane'

type ExtractContentItem = {
  title?: string
  url?: string
}

function itemsFromSnapshot(
  snap: DomSnapshot,
  mediaHints: MediaHint[],
  jsonPreviews: Array<{ url: string; preview: string }>
): PageListItem[] {
  return extractPageList({
    snapshotContent: snap.content,
    snapshotHeader: snap.header,
    snapshotFooter: snap.footer,
    pageUrl: snap.url,
    frames: snap.frames,
    mediaHints,
    jsonPreviews,
  })
}

function domItemsToPageList(items: ExtractContentItem[], pageUrl?: string): PageListItem[] {
  const out: PageListItem[] = []
  for (const item of items) {
    const title = item.title?.trim()
    if (!title || isSiteNavChromeTitle(title, pageUrl ?? item.url)) continue
    if (!isLikelyVideoEntryTitle(title) && !item.url?.match(/\/(vod|video|play|watch|view|detail)/i)) continue
    out.push({
      title,
      pageUrl: item.url,
      mediaUrls: [],
    })
    if (out.length >= 48) break
  }
  return out
}

function mergeItems(primary: PageListItem[], extra: PageListItem[]): PageListItem[] {
  const out: PageListItem[] = []
  const seen = new Set<string>()
  for (const item of [...primary, ...extra]) {
    const key = (item.pageUrl ?? item.title).slice(0, 96)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(item)
    if (out.length >= 48) break
  }
  return out
}

function countUseful(items: PageListItem[]): number {
  return items.filter((item) => isLikelyVideoEntryTitle(item.title) || item.mediaUrls.length > 0).length
}

/** Unified extract for `browser_observe extract` / `system_extract_page`. */
export async function runSystemExtractPage(input: {
  snap: DomSnapshot
  dom: DomPlane
  network?: { list: (opts: { limit?: number }) => Promise<{ ok: boolean; data?: Array<{ url: string; bodyPreview?: string }> }> }
  limit?: number
}): Promise<{ items: PageListItem[]; snap: DomSnapshot }> {
  let snap = input.snap
  let mediaHints: MediaHint[] = []
  const jsonPreviews: Array<{ url: string; preview: string }> = []
  if (input.network) {
    const listed = await input.network.list({ limit: 80 })
    if (listed.ok && listed.data) {
      mediaHints = mediaHintsFromUrls(listed.data)
      for (const event of listed.data) {
        if (event.bodyPreview) jsonPreviews.push({ url: event.url, preview: event.bodyPreview })
      }
    }
  }

  let items = itemsFromSnapshot(snap, mediaHints, jsonPreviews)
  const requested = Math.min(48, Math.max(1, Math.floor(input.limit ?? 16)))

  const needsDom =
    countUseful(items) < Math.min(3, requested) && typeof input.dom.extractContent === 'function'

  if (needsDom && input.dom.scroll) {
    for (let pass = 0; pass < 2 && countUseful(items) < 1; pass += 1) {
      await input.dom.scroll({ y: 720 }).catch(() => undefined)
      await input.dom.wait?.({ kind: 'stable', timeoutMs: 2500 }).catch(() => undefined)
      const refreshed = await input.dom.snapshot?.({ mode: 'viewport' })
      if (refreshed?.ok) snap = refreshed.data
      items = mergeItems(items, itemsFromSnapshot(snap, mediaHints, jsonPreviews))
    }
  }

  if (needsDom && input.dom.extractContent) {
    const extracted = await input.dom.extractContent(requested)
    if (extracted.ok && extracted.data.items.length) {
      items = mergeItems(items, domItemsToPageList(extracted.data.items, snap.url))
    }
  }

  if (!items.length && mediaHints.length) {
    items = [{ title: '(media only)', mediaUrls: mediaHints.map((h) => h.url) }]
  }

  return { items, snap }
}

export function pageListToToolData(items: PageListItem[]): { items: PageListItem[]; count: number } {
  return { items, count: items.length }
}
