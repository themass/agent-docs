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

function looksLikeFormTitle(title: string): boolean {
  return /^(提交|登录|注册|搜索|search|submit|login|sign\s?in|send|发送|查询)$/i.test(title.trim())
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
  /**
   * Flat merge (media → content → form → nav) for backward compat.
   * Prefer layered fields when presenting to the model.
   */
  items: PageStateItem[]
  navItems?: PageStateItem[]
  contentItems?: PageStateItem[]
  mediaItems?: PageStateItem[]
  formItems?: PageStateItem[]
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

/** Split a flat item list into nav / content / media / form layers. */
export function layerPageStateItems(items: PageStateItem[]): {
  navItems: PageStateItem[]
  contentItems: PageStateItem[]
  mediaItems: PageStateItem[]
  formItems: PageStateItem[]
} {
  const navItems: PageStateItem[] = []
  const contentItems: PageStateItem[] = []
  const mediaItems: PageStateItem[] = []
  const formItems: PageStateItem[] = []
  for (const item of items) {
    const title = item.title?.trim() ?? ''
    if (!title) continue
    if (looksLikeFormTitle(title)) {
      formItems.push(item)
      continue
    }
    // Ultra-short titles stay content (not nav noise). Clear nav chrome → nav layer.
    if (/^分类导航/.test(title) || (title.length >= 2 && isNavLikeFeedTitle(title))) {
      navItems.push(item)
      continue
    }
    if (looksLikeMediaTitle(title) || /\d{1,2}:\d{2}/.test(title)) {
      mediaItems.push(item)
      continue
    }
    contentItems.push(item)
  }
  return { navItems, contentItems, mediaItems, formItems }
}

function mergeLayers(layers: {
  navItems: PageStateItem[]
  contentItems: PageStateItem[]
  mediaItems: PageStateItem[]
  formItems: PageStateItem[]
}): PageStateItem[] {
  const ordered: PageStateItem[] = []
  const seen = new Set<string>()
  const push = (item: PageStateItem) => {
    const key = item.title.trim().slice(0, 48).toLowerCase()
    if (!key || seen.has(key) || ordered.length >= 12) return
    seen.add(key)
    ordered.push(item)
  }
  // Media first so nav cannot crowd out actionable cards (existing enrich order).
  for (const item of layers.mediaItems) push(item)
  for (const item of layers.contentItems) push(item)
  for (const item of layers.formItems) push(item)
  for (const item of layers.navItems) push(item)
  return ordered
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

  const emptyLayers = { navItems: [], contentItems: [], mediaItems: [], formItems: [] }
  if (role === 'login') {
    return {
      url: input.url,
      title: input.title,
      role,
      blocked: true,
      items: [],
      ...emptyLayers,
    }
  }

  const layers = layerPageStateItems(input.items)
  const items = mergeLayers(layers).slice(0, 12)
  return {
    url: input.url,
    title: input.title,
    role,
    blocked: Boolean(input.blocking),
    items,
    navItems: layers.navItems.slice(0, 8),
    contentItems: layers.contentItems.slice(0, 12),
    mediaItems: layers.mediaItems.slice(0, 12),
    formItems: layers.formItems.slice(0, 6),
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
  const ordered: PageStateItem[] = []
  const indexByKey = new Map<string, number>()

  const remember = (item: PageStateItem): void => {
    const title = item.title?.trim()
    if (!title) return
    const key = titleKey(title)
    const at = indexByKey.get(key)
    if (at != null) {
      const existing = ordered[at]!
      if (existing.clickIndex == null && item.clickIndex != null) existing.clickIndex = item.clickIndex
      if (!existing.url && item.url) existing.url = item.url
      return
    }
    if (ordered.length >= 12) return
    indexByKey.set(key, ordered.length)
    ordered.push({ ...item, title })
  }

  // Media cards are more actionable than category/navigation containers.
  // Insert them before the 12-item cap so nav rows cannot hide the videos.
  for (const row of mediaCards) remember(row)
  for (const item of items) remember(item)
  for (const row of indexed) remember({ title: row.title, clickIndex: row.index })

  if (ordered.length < 2) {
    for (const label of extractFeedLabelsFromSnapshot(snap as DomSnapshot, 16)) {
      if (isNavLikeFeedTitle(label) || indexByKey.has(titleKey(label))) continue
      remember({ title: label })
      if (ordered.length >= 8) break
    }
  }

  return ordered
}

function formatLayer(name: string, items: PageStateItem[]): string[] {
  if (!items.length) return [`${name}: (none)`]
  const lines = [`${name}:`]
  for (const item of items.slice(0, 8)) {
    const click = item.clickIndex != null ? ` click_index=${item.clickIndex}` : ''
    lines.push(`- ${item.title}${item.url ? ` ${item.url}` : ''}${click}`)
  }
  return lines
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
    return lines.join('\n')
  }

  const hasLayers =
    (state.mediaItems?.length ?? 0) +
      (state.contentItems?.length ?? 0) +
      (state.navItems?.length ?? 0) +
      (state.formItems?.length ?? 0) >
    0

  if (hasLayers) {
    lines.push(...formatLayer('media', state.mediaItems ?? []))
    lines.push(...formatLayer('content', state.contentItems ?? []))
    lines.push(...formatLayer('nav', state.navItems ?? []))
    lines.push(...formatLayer('form', state.formItems ?? []))
  } else if (state.items.length === 0) {
    lines.push('list: (none)')
  } else {
    lines.push('list:')
    for (const item of state.items) {
      const click = item.clickIndex != null ? ` click_index=${item.clickIndex}` : ''
      lines.push(`- ${item.title}${item.url ? ` ${item.url}` : ''}${click}`)
    }
  }

  const clicks = state.items
    .filter((item) => item.clickIndex != null)
    .slice(0, 8)
    .map((item) => `${item.clickIndex}→${item.title.slice(0, 32)}`)
  if (clicks.length) {
    lines.push(`feed_clicks: ${clicks.join('; ')}`)
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
