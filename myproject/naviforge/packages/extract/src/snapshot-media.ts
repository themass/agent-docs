/** Host-agnostic snapshot parsing + media-feed title heuristics (SPA vod home pages). */

export type SnapshotParts = {
  header?: string
  content: string
  footer?: string
}

const NAV_NOISE =
  /^(登录|注册|sign|register|home|首页|热门|直播|安装|更多|未命名|\*{3}|axx\.|http|www\.)/i

const FEED_LABEL_NOISE =
  /^(登录|注册|sign in|home|\*{3}|\.{3}|axx\.|http|www\.|当前页|Start of page|End of page|\[\d+\])/i

function snapshotBlob(parts: SnapshotParts): string {
  return [parts.header, parts.content, parts.footer].filter(Boolean).join('\n')
}

function stripSnapshotMarkup(title: string): string {
  return title
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

/** Legacy a11y lines: `[1] link "Title"`. */
export function parseLegacySnapshotItems(content: string): Array<{ index: number; title: string }> {
  const LINE_ITEM = /^\[(\d+)\]\s+(\w+)(?:\s+"([^"]*)")?/
  const items: Array<{ index: number; title: string }> = []
  for (const line of content.split('\n')) {
    const match = LINE_ITEM.exec(line.trim())
    if (!match) continue
    const title = match[3]?.trim() || match[2]
    if (!title || (/button|nav|menu|logo/i.test(title) && title.length < 4)) continue
    items.push({ index: Number(match[1]), title })
  }
  return items.slice(0, 48)
}

/** Modern indexed snapshots: `*[12]<div >…` / `[12]<img />`. */
export function parseIndexedSnapshotLines(content: string, limit = 48): Array<{ index: number; title: string }> {
  const out: Array<{ index: number; title: string }> = []
  const seen = new Set<number>()
  for (const line of content.split('\n')) {
    const trimmed = line.trim()
    const star = /^\*\[(\d+)\]\s*(.+)$/.exec(trimmed)
    const plain = /^\[(\d+)\]\s*(.+)$/.exec(trimmed)
    const match = star ?? plain
    if (!match) continue
    const index = Number(match[1])
    if (seen.has(index)) continue
    const title = match[2].replace(/\*\[\d+\]/g, '').trim()
    if (title.length < 2 || NAV_NOISE.test(title)) continue
    if (/register|login|signin/i.test(title)) continue
    const plainTitle = stripSnapshotMarkup(title)
    if (/^(热销|限时|热门|精品|官方)(专题|专区)/.test(plainTitle)) continue
    if (/专题\s*$/.test(plainTitle) && plainTitle.length <= 20) continue
    seen.add(index)
    out.push({ index, title })
    if (out.length >= limit) break
  }
  return out
}

export function isTopicBucketSnapshotTitle(title: string): boolean {
  const raw = title.trim()
  const t = stripSnapshotMarkup(raw)
  if (t.length < 2) return true
  if (/^<a\s*\/>|^<img\s*\/>|^<span/i.test(raw)) return true
  if (/^(热销|限时|热门|精品|官方|另类|在线|有声|特色)(专题|专区|推荐|电影|小说)/.test(t)) return true
  if (/^(最热门|精品推荐|官方推荐)$/.test(t)) return true
  if (/专题\s*$/.test(t) && t.length <= 16) return true
  if (/专区\s*2?$/.test(t) && t.length <= 12) return true
  if (/^[\w-]+(\.[\w-]+)+$/i.test(t) && !/\s/.test(t) && t.length <= 48) return true
  if (/^(登录|注册|register|sign\s*in|sign\s*up)$/i.test(t)) return true
  if (/^\[Start of page\]|^Current Page:/i.test(t)) return true
  return false
}

export function isLikelyVideoEntryTitle(title: string): boolean {
  const raw = title.trim()
  const t = stripSnapshotMarkup(raw)
  if (t.length < 2 || isTopicBucketSnapshotTitle(t)) return false
  if (/\/>$/.test(raw) && t.length >= 8) return true
  if (/\d{1,2}:\d{2}/.test(t)) return true
  if (/[~…！？!?：:—\-]/.test(t)) return true
  if (t.length >= 14) return true
  if (t.length >= 10 && /[A-Za-z0-9]/.test(t) && /[\u4e00-\u9fff]/.test(t)) return true
  return false
}

function pushDurationAdjacentTitle(out: string[], seen: Set<string>, raw: string, limit: number): void {
  if (out.length >= limit) return
  const title = stripSnapshotMarkup(raw)
  if (title.length < 6 || isTopicBucketSnapshotTitle(title)) return
  if (classifyDurationLine(title)) return
  const key = title.slice(0, 48)
  if (seen.has(key)) return
  seen.add(key)
  out.push(title)
}

function classifyDurationLine(text: string): boolean {
  return /^\d{1,2}:\d{2}(?::\d{2})?$/.test(text.trim())
}

function pushVideoTitle(out: string[], seen: Set<string>, raw: string, limit: number): void {
  if (out.length >= limit) return
  if (!isLikelyVideoEntryTitle(raw)) return
  const title = stripSnapshotMarkup(raw)
  const key = title.slice(0, 48)
  if (seen.has(key)) return
  seen.add(key)
  out.push(title)
}

function extractFeedLabelsFromBlob(blob: string, limit: number): string[] {
  const lines = blob
    .split(/\n+/)
    .map((line) => line.replace(/\*\[\d+\]/g, '').trim())
    .filter((line) => line.length >= 3 && line.length <= 120)
  const out: string[] = []
  const seen = new Set<string>()
  for (const line of lines) {
    if (FEED_LABEL_NOISE.test(line)) continue
    if (!/[\u4e00-\u9fffA-Za-z0-9]/.test(line)) continue
    if (/^(热销|限时|热门|专题|专区)/.test(line) && line.length < 12) continue
    if (/^(热销|限时|热门|精品|官方)(专题|专区)/.test(line)) continue
    const key = line.slice(0, 64)
    if (seen.has(key)) continue
    seen.add(key)
    out.push(line)
    if (out.length >= limit) break
  }
  return out
}

/** Titles from duration blocks, HD rows, and indexed snapshot lines — not category chips. */
export function collectMediaFeedTitlesFromParts(parts: SnapshotParts, limit = 24): string[] {
  const blob = snapshotBlob(parts)
  const fromLabels = extractFeedLabelsFromBlob(blob, limit * 2)
  const out: string[] = []
  const seen = new Set<string>()
  for (const label of fromLabels) {
    if (/^(Current Page|Interactive elements|Start of page|End of page)/i.test(label)) continue
    pushVideoTitle(out, seen, label, limit)
  }
  const blobLines = blob.split('\n').map((line) => line.replace(/\*\[\d+\]/g, '').trim())
  for (let i = 0; i < blobLines.length; i += 1) {
    const line = blobLines[i] ?? ''
    if (/^\d{1,2}:\d{2}(?::\d{2})?$/.test(line)) {
      pushDurationAdjacentTitle(out, seen, blobLines[i + 1] ?? '', limit)
      continue
    }
    if (line === 'HD' && /^\d{1,2}:\d{2}/.test(blobLines[i + 1] ?? '')) {
      pushDurationAdjacentTitle(out, seen, blobLines[i + 2] ?? '', limit)
    }
  }
  for (const row of parseIndexedSnapshotLines(blob, 80)) {
    pushVideoTitle(out, seen, row.title, limit)
  }
  return out
}

export function isSiteNavChromeTitle(title: string, pageUrl?: string): boolean {
  const t = stripSnapshotMarkup(title)
  if (/^(登录|注册|register|sign\s*in)$/i.test(t)) return true
  if (/^未命名\s·/.test(t)) return true
  if (!pageUrl) return false
  try {
    const host = new URL(pageUrl).hostname.replace(/^www\./, '')
    const bare = t.replace(/^www\./, '')
    if (bare === host || bare.endsWith(host)) return true
    const path = new URL(pageUrl).pathname
    if (/^\/(home|register|login|user\/info)\/?$/i.test(path) && (bare === host || /^未命名/.test(t))) return true
  } catch {
    /* ignore */
  }
  return false
}
