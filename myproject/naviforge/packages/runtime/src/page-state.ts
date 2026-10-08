import type { DomSnapshot } from '@naviforge/dom-plane'

import { extractFeedLabelsFromSnapshot } from './page-feed-evidence.js'
import { isNavLikeFeedTitle, parseIndexedSnapshotLines } from './snapshot-index-lines.js'

export type PageStateRole = 'login' | 'list' | 'home' | 'detail' | 'unknown'

export type PageStateItem = { title: string; url?: string; clickIndex?: number }

function stripSnapshotMarkup(title: string): string {
  return title.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
}

function looksLikeMediaTitle(title: string): boolean {
  const text = stripSnapshotMarkup(title)
  if (text.length < 8) return false
  if (/^(HD|SD|猫咪官方|官方|更多|推荐|热门|经典动漫)$/i.test(text)) return false
  if (/^·?\s*[\d.]+万?次观看$/.test(text)) return false
  return /\d{1,2}:\d{2}(?::\d{2})?/.test(text) || text.length >= 14
}

/** Recover cards whose accessibility tree indexes only the image, not its text. */
export function extractIndexedMediaCards(
  snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>,
  limit = 12
): PageStateItem[] {
  const lines = [snap.header, snap.content, snap.footer]
    .filter(Boolean)
    .join('\n')
    .split(/\n+/)
  const indexed = /^\*?\[(\d+)\]\s*(.*)$/
  const cards: PageStateItem[] = []
  for (let i = 0; i < lines.length && cards.length < limit; i += 1) {
    const current = indexed.exec(lines[i]?.trim() ?? '')
    if (!current || !/^<(?:img|a)\b/i.test(current[2].trim())) continue
    const following: string[] = []
    for (let j = i + 1; j < lines.length; j += 1) {
      if (indexed.test(lines[j]?.trim() ?? '')) break
      const line = lines[j]?.trim() ?? ''
      if (line) following.push(line)
    }
    const duration = following.find((line) => /^\d{1,2}:\d{2}(?::\d{2})?$/.test(line))
    const title = following.find((line) => looksLikeMediaTitle(line) && line !== duration)
    if (!title) continue
    cards.push({
      title: stripSnapshotMarkup(title),
      clickIndex: Number(current[1]),
    })
  }
  return cards
}

export type PageState = {
  url: string
  title: string
  role: PageStateRole
  /** Login or captcha wall — do not treat link harvest as site structure. */
  blocked: boolean
  items: PageStateItem[]
}

export function looksLikeLoginUrl(url: string): boolean {
  try {
    return /\/(login|signin|sign-in|auth)(\/|$)/i.test(new URL(url).pathname)
  } catch {
    return /login|signin/i.test(url)
  }
}

export function looksLikeHomeUrl(url: string): boolean {
  try {
    const path = new URL(url).pathname.replace(/\/$/, '')
    return path === '' || path === '/home' || path === '/index'
  } catch {
    return false
  }
}

export function classifyPageState(input: {
  url: string
  title: string
  login: boolean
  blocking: boolean
  items: PageStateItem[]
}): PageState {
  const blocked = input.login || input.blocking || looksLikeLoginUrl(input.url)
  let role: PageStateRole = 'unknown'
  if (blocked && (input.login || looksLikeLoginUrl(input.url))) role = 'login'
  else if (input.items.length >= 2) role = 'list'
  else if (looksLikeHomeUrl(input.url)) role = 'home'
  else if (input.items.length === 1) role = 'detail'
  return {
    url: input.url,
    title: input.title,
    role,
    blocked: role === 'login' || input.blocking,
    items: role === 'login' ? [] : input.items.slice(0, 12),
  }
}

function titleKey(title: string): string {
  return title.trim().slice(0, 48).toLowerCase()
}

/** Merge structured extract with snapshot indices / feed labels (SPA feeds with empty extract). */
export function enrichItemsWithSnapshotFeed(
  items: PageStateItem[],
  snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>
): PageStateItem[] {
  const indexed = parseIndexedSnapshotLines(snap)
  const mediaCards = extractIndexedMediaCards(snap)
  const byTitle = new Map<string, PageStateItem>()
  for (const item of items) {
    if (!item.title?.trim()) continue
    byTitle.set(titleKey(item.title), { ...item })
  }

  // Media cards are more actionable than category/navigation containers. Add
  // them first so the 12-item page-state cap cannot hide the actual videos.
  for (const row of mediaCards) {
    byTitle.set(titleKey(row.title), row)
  }

  for (const row of indexed) {
    const key = titleKey(row.title)
    const existing = byTitle.get(key)
    if (existing) {
      if (existing.clickIndex == null) existing.clickIndex = row.index
      continue
    }
    if (byTitle.size >= 12) continue
    byTitle.set(key, { title: row.title, clickIndex: row.index })
  }

  if (byTitle.size < 2) {
    for (const label of extractFeedLabelsFromSnapshot(snap as DomSnapshot, 16)) {
      const key = titleKey(label)
      if (byTitle.has(key) || isNavLikeFeedTitle(label)) continue
      byTitle.set(key, { title: label })
      if (byTitle.size >= 8) break
    }
  }

  return [...byTitle.values()].slice(0, 12)
}

export function formatPageState(state: PageState): string {
  const lines = [
    'PAGE STATE:',
    `url: ${state.url}`,
    `title: ${state.title || '(untitled)'}`,
    `role: ${state.role}`,
    state.blocked ? 'blocked: login' : 'blocked: no',
  ]
  if (state.role === 'login') {
    lines.push('list: (none — login wall)')
  } else if (state.items.length === 0) {
    lines.push('list: (none)')
  } else {
    lines.push('list:')
    for (const item of state.items) {
      const click =
        item.clickIndex != null ? ` click_index=${item.clickIndex}` : ''
      lines.push(`- ${item.title}${item.url ? ` ${item.url}` : ''}${click}`)
    }
    const clicks = state.items
      .filter((item) => item.clickIndex != null)
      .slice(0, 8)
      .map((item) => `${item.clickIndex}→${item.title.slice(0, 32)}`)
    if (clicks.length) {
      lines.push(`feed_clicks: ${clicks.join('; ')}`)
    }
  }
  return lines.join('\n')
}

/** Same login page, same link harvest — skip. Page state already describes the wall. */
export function shouldSkipLoginLinkRead(input: {
  tool: string
  args?: Record<string, unknown>
  page?: PageState | null
  snapUrl: string
}): boolean {
  if (!input.page || input.page.role !== 'login') return false
  if (!input.snapUrl || input.page.url !== input.snapUrl) return false
  const tool = input.tool
  const mode = typeof input.args?.mode === 'string' ? input.args.mode : ''
  const kind = typeof input.args?.kind === 'string' ? input.args.kind : ''
  const action = typeof input.args?.action === 'string' ? input.args.action : ''
  if (tool === 'dom_extract_dom') return kind === 'links' || kind === '' || kind === 'all'
  if (tool === 'browser_observe' && (action === 'read' || action === '')) {
    return mode === 'dom' || kind === 'links'
  }
  if (tool !== 'dom_read') return false
  return mode === 'dom' || kind === 'links'
}
