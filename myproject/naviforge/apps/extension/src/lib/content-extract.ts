/**
 * Generic list extraction: induce the repeating record structure of a page,
 * then read fields out of it. Site knowledge is data (`SiteProfile`), never code.
 *
 * Split in two halves on purpose:
 *  - `collectCandidates` reads the DOM into plain JSON and does no thinking.
 *  - `extractContent` is pure and does all the thinking, so it is testable
 *    without a DOM and injectable output can be snapshotted.
 */

export type Candidate = {
  index: number
  tag: string
  href?: string
  /** aria-label / title attribute of the link itself. */
  label?: string
  /** Normalized ancestor signature — records of one list share it. */
  path: string
  /** Readable text fragments inside the record. */
  texts: string[]
  /** Text of nested links other than the record link (author, shop, source). */
  linkTexts: string[]
  /** Top-document coordinates: frame offset and page scroll folded in, so records
   *  collected across scroll positions and frames sort into one reading order. */
  rect: { top: number; left: number; width: number; height: number }
  hasMedia: boolean
  /** Inside header / nav / footer / aside. */
  inChrome: boolean
  /** Inside a carousel, banner or ad container. */
  inBanner: boolean
  visible: boolean
}

export type ContentItem = {
  rank: number
  index: number
  title: string
  url?: string
  fields: Record<string, string>
  confidence: number
  reason: string
}

export type ExtractReport = {
  items: ContentItem[]
  requested: number
  found: number
  /** Set when fewer records were found than requested — never pad the list. */
  shortfall?: string
  strategy: 'profile' | 'induced' | 'fallback'
  profileId?: string
  groupSize: number
  /** Dominant link shape of the record group — the seed for a learned profile. */
  pattern?: string
  /** Shared ancestor signature of the winning record group — seed for profile.record. */
  recordPath?: string
}

export type SiteProfile = {
  id: string
  host: string[]
  /** Record links must match this pattern — kills promo and activity outliers. */
  detailUrl?: string
  /** Keep only records inside this container — for pages induction groups wrong. */
  record?: string
  /** Drop records inside this container. */
  exclude?: string
  minGroup?: number
  source: 'bundled' | 'learned' | 'user'
}

/** Generic chrome/banner containers — safe default for learned exclude. */
export const DEFAULT_PROFILE_EXCLUDE =
  'header, nav, footer, .carousel, [class*="banner"], [class*="swiper"], [class*="promo"]'

/**
 * Site knowledge lives here as data. A profile may only narrow the generic
 * result; it can never bypass the readable-title and valid-url gates below.
 */
export const BUNDLED_PROFILES: SiteProfile[] = [
  {
    id: 'bilibili-video',
    host: ['bilibili.com'],
    detailUrl: '/video/[A-Za-z0-9]+',
    source: 'bundled',
  },
  {
    id: 'douban-movie',
    host: ['douban.com'],
    detailUrl: '/subject/\\d+',
    record: 'ol.grid-view, .article',
    exclude: DEFAULT_PROFILE_EXCLUDE,
    source: 'bundled',
  },
  {
    id: 'github-repo',
    host: ['github.com'],
    detailUrl: 'github\\.com/[^/]+/[^/]+',
    record: 'main,[role=main],#js-pjax-container',
    exclude: `${DEFAULT_PROFILE_EXCLUDE},[data-testid="header"]`,
    source: 'bundled',
  },
  {
    id: 'bbc-news',
    host: ['bbc.com'],
    detailUrl: '/news/(articles|videos|live)/',
    exclude: DEFAULT_PROFILE_EXCLUDE,
    source: 'bundled',
  },
]

export function profileFor(url: string, profiles: SiteProfile[] = BUNDLED_PROFILES): SiteProfile | undefined {
  let host: string
  let pathname: string
  try {
    const parsed = new URL(url)
    host = parsed.hostname
    pathname = parsed.pathname
  } catch {
    return undefined
  }
  const profile = profiles.find((item) =>
    item.host.some((candidate) => host === candidate || host.endsWith(`.${candidate}`))
  )
  // GitHub repo home is read-page territory; file-tree rows are not a content feed.
  if (profile?.id === 'github-repo' && /^\/[^/]+\/[^/]+\/?$/.test(pathname)) return undefined
  return profile
}

const PLACEHOLDER = /^\[\d+\]\s*<[a-z][^>]*\/?>$/i
const SNAPSHOT_NODE = /^\[\d+\]\s*<[a-z][^>]*>.*\/>$/i
const NAV_WORD =
  /^(首页|热门|番剧|直播|游戏|会员|登录|注册|下载|更多|全部|展开|收起|查看更多|home|more|login|sign ?in|menu|search|next|prev)$/i
const CONTROL_WORD =
  /^(稍后再看|稍后观看|收藏|取消收藏|分享|举报|不感兴趣|watch later|save|saved|share|report|more actions?)$/i

/** Gambling / CPA promos common on CN video aggregators — never list items. */
const PROMO_TEXT =
  /注册即送|开元棋牌|PG电子|葡京|银河|体育|棋牌|首存|送888|暴击|官方送|爆款福利|澳门|博彩|\.vip\b/i
const PROMO_HOST = /\.vip\b|xn--|8888|casino|bet\d|jjzdsq|myxuanxuan/i

function pageOrigin(base?: string): string | undefined {
  if (!base) return undefined
  try {
    return new URL(base).origin
  } catch {
    return undefined
  }
}

function isSameOrigin(href: string | undefined, base?: string): boolean {
  if (!href || !base) return false
  try {
    return new URL(href, base).origin === new URL(base).origin
  } catch {
    return false
  }
}

function promoText(candidate: Candidate): string {
  return [candidate.label ?? '', ...candidate.texts, ...candidate.linkTexts].join(' ')
}

function isPromoCandidate(candidate: Candidate, base?: string): boolean {
  if (PROMO_TEXT.test(promoText(candidate))) return true
  if (!candidate.href) return false
  try {
    const host = new URL(resolveRecordHref(candidate.href, base)).hostname
    if (PROMO_HOST.test(host)) return true
  } catch {
    return true
  }
  if (base && !isSameOrigin(candidate.href, base)) return true
  return false
}

/** Infer detail URL shape from same-origin links (e.g. /vod/view/ID on aggregator sites). */
export function inferDetailUrlPattern(candidates: Candidate[], base: string): RegExp | undefined {
  const counts = new Map<string, number>()
  const rules: Array<[string, RegExp]> = [
    ['vod-view', /\/vod\/view\/[^/?#]+/i],
    ['bilibili', /\/video\/[A-Za-z0-9]+/i],
    ['watch', /\/watch(?:\/|\?)/i],
  ]
  for (const item of candidates) {
    if (!item.href || !isSameOrigin(item.href, base)) continue
    const href = resolveRecordHref(item.href, base)
    for (const [key, re] of rules) {
      if (re.test(href)) counts.set(key, (counts.get(key) ?? 0) + 1)
    }
  }
  const best = [...counts.entries()].sort((a, b) => b[1] - a[1])[0]
  if (!best || best[1] < 3) return undefined
  return rules.find(([key]) => key === best[0])?.[1]
}

/** Value-shape field detectors — deliberately class-name free so they port across sites. */
const FIELD_RULES: Array<{ name: string; test: RegExp }> = [
  { name: 'duration', test: /^\d{1,3}:\d{2}(:\d{2})?$/ },
  { name: 'views', test: /^[\d.,]+\s*[万亿kKmM]\+?\s*(次)?\s*(播放|观看|views?)?$/ },
  { name: 'views', test: /^[\d.,]+\s*(次)?\s*(播放|观看|views?|watching)$/i },
  { name: 'price', test: /^[¥$€£₩]\s?[\d.,]+$|^[\d.,]+\s*(元|円)$/ },
  { name: 'rating', test: /^(10(\.0)?|\d\.\d)\s*(分)?$/ },
  { name: 'date', test: /^\d{4}[-/.年]\d{1,2}([-/.月]\d{1,2}日?)?$/ },
  { name: 'date', test: /^(19|20)\d{2}$/ },
  { name: 'date', test: /^\d+\s*(分钟|小时|天|周|个月|年)前$/ },
  { name: 'date', test: /^\d+\s+(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+ago$/i },
  { name: 'episode', test: /^(第\s?\d+\s?[集话季]|更新至第?\s?\d+\s?[集话]|EP\s?\d+|S\d+E\d+)$/i },
  // After year dates: bare integers are usually danmaku/likes, never titles.
  { name: 'count', test: /^\d{2,6}$/ },
]

function classify(text: string): string | undefined {
  return FIELD_RULES.find((rule) => rule.test.test(text))?.name
}

function readable(text: string | undefined): string | undefined {
  const value = text?.replace(/\s+/g, ' ').trim()
  if (!value || value.length < 2 || value.length > 300) return undefined
  if (
    PLACEHOLDER.test(value) ||
    SNAPSHOT_NODE.test(value) ||
    NAV_WORD.test(value) ||
    CONTROL_WORD.test(value)
  ) {
    return undefined
  }
  if (classify(value)) return undefined
  return value.slice(0, 160)
}

/**
 * Generalize a href into a shape so records of one list vote on a common
 * pattern. Id-like segments collapse, which is what separates `/video/BV1x..`
 * cards from a `/blackboard/era/activity.html` promo without knowing either.
 */
export function urlPattern(href: string, base?: string): string {
  try {
    const url = new URL(resolveRecordHref(href, base), base)
    const path = url.pathname
      .split('/')
      .map((segment) => (segment.length >= 4 && /\d/.test(segment) ? '*' : segment))
      .join('/')
    const query = [...url.searchParams.keys()].sort().join('&')
    return `${url.hostname}${path}${query ? `?${query}` : ''}`
  } catch {
    return href
  }
}

/** Unwrap auth-wall redirects (e.g. GitHub trending when logged out). */
export function resolveRecordHref(href: string, base?: string): string {
  try {
    const url = new URL(href, base)
    if (
      (url.pathname === '/login' || url.pathname.endsWith('/login')) &&
      url.searchParams.has('return_to')
    ) {
      return new URL(url.searchParams.get('return_to')!, url.origin).href
    }
    return url.href
  } catch {
    return href
  }
}

function hrefMatchesDetail(href: string, detail: RegExp, base?: string): boolean {
  return detail.test(href) || detail.test(resolveRecordHref(href, base))
}

function titleScore(text: string): number {
  if (/^\d+[.,]?\d*(?:[万亿kKmM]\+?)?$/.test(text)) return -1_000
  const digits = (text.match(/\d/g) ?? []).length
  return (digits / text.length > 0.6 ? -50 : 0) + text.length
}

/** Turn an induced ancestor signature into a CSS container selector. */
export function pathToRecordSelector(path: string): string | undefined {
  const parts = path.split('>').filter(Boolean)
  if (parts.length < 2) return undefined
  return parts.slice(0, -1).join('>')
}

/** Longest tag-level prefix shared by every path in a record group. */
export function dominantPathPrefix(paths: string[]): string | undefined {
  if (!paths.length) return undefined
  const split = paths.map((path) => path.split('>').filter(Boolean))
  const minLen = Math.min(...split.map((parts) => parts.length))
  if (minLen < 2) return undefined
  const prefix: string[] = []
  for (let index = 0; index < minLen - 1; index += 1) {
    const segment = split[0]![index]!
    if (split.every((parts) => parts[index] === segment)) prefix.push(segment)
    else break
  }
  return prefix.length ? prefix.join('>') : undefined
}

function readingOrder(a: Candidate, b: Candidate): number {
  const rowA = Math.round(a.rect.top / 48)
  const rowB = Math.round(b.rect.top / 48)
  if (rowA !== rowB) return rowA - rowB
  if (a.rect.left !== b.rect.left) return a.rect.left - b.rect.left
  return a.index - b.index
}

function groupScore(members: Candidate[]): number {
  const withHref = members.filter((item) => item.href).length
  const withMedia = members.filter((item) => item.hasMedia).length
  const area = members.reduce((sum, item) => sum + item.rect.width * item.rect.height, 0) / members.length
  return members.length * 10 + (withHref / members.length) * 15 + (withMedia / members.length) * 15 + Math.min(area / 20_000, 8)
}

/** Keep only members whose href shape matches the list's dominant shape. */
function dominantPattern(members: Candidate[], base?: string): string | undefined {
  const linked = members.filter((item) => item.href)
  if (linked.length < 4) return undefined
  const counts = new Map<string, number>()
  for (const item of linked) {
    const pattern = urlPattern(item.href as string, base)
    counts.set(pattern, (counts.get(pattern) ?? 0) + 1)
  }
  const [pattern, count] = [...counts].sort((a, b) => b[1] - a[1])[0] as [string, number]
  return count >= Math.max(3, linked.length * 0.6) ? pattern : undefined
}

function buildItem(candidate: Candidate, rank: number, base: string | undefined, reason: string): ContentItem | undefined {
  const fields: Record<string, string> = {}
  const pool: string[] = []
  for (const text of candidate.texts) {
    const value = text.replace(/\s+/g, ' ').trim()
    if (!value) continue
    const field = classify(value)
    if (field) {
      if (!fields[field]) fields[field] = value
      continue
    }
    pool.push(value)
  }

  const author = candidate.linkTexts.map((text) => readable(text)).find(Boolean)
  if (author) fields.author = author

  // Titles are the longest readable string in a record far more often than not,
  // but digit-heavy strings (codes, counts, years) lose to a short real title.
  const fromPool = pool
    .map((text) => readable(text))
    .filter((text): text is string => Boolean(text) && text !== author)
    .sort((a, b) => titleScore(b) - titleScore(a))[0]
  const numericTitle = /^\d+[.,]?\d*(?:[万亿kKmM]\+?)?$/
  const isBadTitle = (text: string): boolean =>
    Boolean(classify(text)) ||
    numericTitle.test(text) ||
    Object.values(fields).includes(text) ||
    !/[\u4e00-\u9fffA-Za-z]/.test(text)
  let title: string | undefined = readable(candidate.label) ?? fromPool
  if (title !== undefined && isBadTitle(title)) {
    title =
      pool
        .map((text) => readable(text))
        .filter(
          (text): text is string =>
            typeof text === 'string' && text !== author && !isBadTitle(text)
        )
        .sort((a, b) => titleScore(b) - titleScore(a))[0] ?? undefined
  }
  if (title === undefined) {
    // Keep the row when we have a detail URL — show BV/id rather than a metric as "title".
    let urlHint: string | undefined
    if (candidate.href) {
      try {
        urlHint = resolveRecordHref(candidate.href, base)
      } catch {
        urlHint = candidate.href
      }
    }
    const bv = urlHint ? /\/video\/(BV[\w]+)/i.exec(urlHint)?.[1] : undefined
    const leaf =
      urlHint &&
      /\/([^/?#]+)\/?$/.exec(new URL(urlHint, base ?? 'https://example.com').pathname)?.[1]
    const id = bv ?? leaf ?? undefined
    title = id ? `未命名 · ${id}` : undefined
  }
  if (title === undefined) return undefined
  if (PROMO_TEXT.test(title)) return undefined

  let url: string | undefined
  if (candidate.href) {
    try {
      url = resolveRecordHref(candidate.href, base)
    } catch {
      url = candidate.href
    }
  }

  let confidence = 0.5
  if (url) confidence += 0.2
  if (readable(candidate.label)) confidence += 0.1
  if (candidate.hasMedia) confidence += 0.1
  confidence += Math.min(Object.keys(fields).length * 0.04, 0.1)

  return {
    rank,
    index: candidate.index,
    title,
    url,
    fields,
    confidence: Math.min(1, Number(confidence.toFixed(2))),
    reason,
  }
}

export function extractContent(
  candidates: Candidate[],
  opts: {
    url?: string
    n?: number
    visibleOnly?: boolean
    profiles?: SiteProfile[]
  } = {}
): ExtractReport {
  const requested = Math.min(48, Math.max(1, Math.floor(opts.n ?? 4)))
  const base = opts.url
  const profile = base ? profileFor(base, opts.profiles ?? BUNDLED_PROFILES) : undefined
  let detail = profile?.detailUrl ? new RegExp(profile.detailUrl) : undefined

  let usable = candidates.filter((item) => {
    if (opts.visibleOnly !== false && !item.visible) return false
    if (item.inChrome || item.inBanner) return false
    if (item.rect.width < 20 || item.rect.height < 10) return false
    return true
  })
  usable = usable.filter((item) => !isPromoCandidate(item, base))

  if (!detail && base) detail = inferDetailUrlPattern(usable, base)

  let pool = detail
    ? usable.filter((item) => !item.href || hrefMatchesDetail(item.href, detail!, base))
    : usable

  if (base && !profile?.detailUrl) {
    const sameOrigin = pool.filter((item) => isSameOrigin(item.href, base))
    if (sameOrigin.length >= (profile?.minGroup ?? 3)) pool = sameOrigin
  }

  const groups = new Map<string, Candidate[]>()
  for (const item of pool) {
    const bucket = groups.get(item.path)
    if (bucket) bucket.push(item)
    else groups.set(item.path, [item])
  }

  const minGroup = profile?.minGroup ?? 3
  const ranked = [...groups.values()].sort((a, b) => groupScore(b) - groupScore(a))
  const best = ranked.find((members) => members.length >= minGroup)

  let members: Candidate[]
  let strategy: ExtractReport['strategy']
  let reason: string
  let pattern: string | undefined

  if (best) {
    pattern = dominantPattern(best, base)
    members = pattern
      ? best.filter((item) => !item.href || urlPattern(item.href, base) === pattern)
      : best
    strategy = profile ? 'profile' : 'induced'
    reason = pattern ? `repeating record group, link shape ${pattern}` : 'repeating record group'
  } else {
    // No repeating structure — take linked, media-bearing nodes in reading order.
    members = pool.filter((item) => item.href && item.hasMedia)
    if (members.length < requested) members = pool.filter((item) => item.href)
    strategy = 'fallback'
    reason = 'no repeating record group — linked nodes in reading order'
  }

  const items: ContentItem[] = []
  const seen = new Set<string>()
  for (const candidate of [...members].sort(readingOrder)) {
    if (items.length >= requested) break
    const item = buildItem(candidate, items.length + 1, base, reason)
    if (!item) continue
    const key = item.url ?? item.title
    if (seen.has(key)) continue
    seen.add(key)
    items.push(item)
  }

  // A learned profile may be wrong on a sibling page. Bundled profiles are
  // curated — never drop them and re-extract unfiltered noise.
  if (!items.length && profile && profile.source !== 'bundled') {
    const rest = (opts.profiles ?? BUNDLED_PROFILES).filter((item) => item.id !== profile.id)
    return extractContent(candidates, { ...opts, profiles: rest })
  }

  const groupSize = best?.length ?? members.length
  const recordPath = best ? dominantPathPrefix(best.map((item) => item.path)) : undefined
  return {
    items,
    requested,
    found: items.length,
    shortfall:
      items.length < requested
        ? `仅找到 ${items.length}/${requested} 条（${
            strategy === 'profile' ? '站点配置' : strategy === 'induced' ? '自动归纳' : '兜底'
          }）— 请把列表滚到可见区域，或调低 Top N`
        : undefined,
    strategy,
    profileId: strategy === 'profile' ? profile?.id : undefined,
    groupSize,
    pattern,
    recordPath,
  }
}

/**
 * Turn a confident induction into a reusable site profile. This is how a
 * one-off page visit becomes a capability instead of a one-off patch.
 */
export function proposeProfile(url: string, report: ExtractReport): SiteProfile | undefined {
  if (report.strategy !== 'induced' || !report.pattern || report.groupSize < 4) return undefined
  let host: string
  try {
    host = new URL(url).hostname
  } catch {
    return undefined
  }
  const split = report.pattern.indexOf('/')
  if (split < 0 || report.pattern.slice(0, split) !== host) return undefined
  const path = (report.pattern.slice(split).split('?')[0] ?? '').replace(/\/+$/, '')
  if (path.length < 2) return undefined
  const detailUrl = path
    .split('*')
    .map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('[^/]+')
  const record = report.recordPath
  return {
    id: `learned-${host}`,
    host: [host],
    detailUrl,
    record,
    exclude: DEFAULT_PROFILE_EXCLUDE,
    source: 'learned',
  }
}

/* ---------------------------------------------------------------------------
 * DOM adapter. Self-contained by design so it can be injected verbatim with
 * `page.evaluate(collectCandidates)` in tests and into MAIN-world frames later.
 * ------------------------------------------------------------------------- */

/** A selector from learned or user-authored data is untrusted input. */
function validSelector(selector: string | undefined): string | undefined {
  if (!selector) return undefined
  try {
    if (typeof document !== 'undefined') document.querySelector(selector)
    return selector
  } catch {
    return undefined
  }
}

/**
 * Narrow the candidate entries with a profile's CSS hints. This is the escape
 * hatch for pages where induction groups the wrong thing — a profile can shrink
 * the pool it induces over, but never inject records the page does not have.
 * Filtering entries (rather than re-querying) keeps snapshot indexes intact, so
 * anything extracted here can still be marked.
 */
export function narrowEntries<T extends { element: Element }>(
  entries: T[],
  profile?: SiteProfile
): T[] {
  const record = validSelector(profile?.record)
  const exclude = validSelector(profile?.exclude)
  if (!record && !exclude) return entries
  return entries.filter(({ element }) => {
    if (typeof element?.closest !== 'function') return false
    if (record && !element.closest?.(record)) return false
    if (exclude && element.closest?.(exclude)) return false
    return true
  })
}

/** Same-origin iframes and open shadow roots — mirrors what PageController indexes. */
export function gatherInteractiveElements(
  root: Document | undefined = typeof document !== 'undefined' ? document : undefined
): Element[] {
  const seen = new Set<Element>()
  const out: Element[] = []
  if (!root) return out
  const INTERACTIVE_SEL = 'a[href],[role="link"]'
  const visitRoot = (scope: Document | ShadowRoot) => {
    for (const element of scope.querySelectorAll(INTERACTIVE_SEL)) {
      if (!(element instanceof Element) || seen.has(element)) continue
      seen.add(element)
      out.push(element)
    }
    for (const host of scope.querySelectorAll('*')) {
      if (host.shadowRoot) visitRoot(host.shadowRoot)
    }
    if (scope instanceof Document) {
      for (const frame of scope.querySelectorAll('iframe')) {
        try {
          const inner = frame.contentDocument
          if (inner) visitRoot(inner)
        } catch {
          // cross-origin frame
        }
      }
    }
  }
  visitRoot(root)
  return out
}

export function collectCandidates(
  entries?: Array<{ index: number; element: Element; title?: string }>
): Candidate[] {
  const CHROME = 'header,nav,footer,aside,[role=navigation],[role=banner],[role=contentinfo]'
  const BANNER =
    '[class*="banner"],[class*="carousel"],[class*="swiper"],[class*="promo"],[class*="advert"],[aria-roledescription="carousel"],ins.adsbygoogle,[data-ad]'

  const SHOW_TEXT = 4 // NodeFilter.SHOW_TEXT, inlined to keep this injectable.
  const doc = typeof document !== 'undefined' ? document : undefined

  const gathered: Element[] = []
  if (!entries && doc) {
    const seen = new Set<Element>()
    const queue: Array<Document | ShadowRoot> = [doc]
    while (queue.length) {
      const scope = queue.pop()!
      for (const element of scope.querySelectorAll('a[href],[role="link"]')) {
        if (!(element instanceof Element) || seen.has(element)) continue
        seen.add(element)
        gathered.push(element)
      }
      for (const host of scope.querySelectorAll('*')) {
        if (host.shadowRoot) queue.push(host.shadowRoot)
      }
      if (scope instanceof Document) {
        for (const frame of scope.querySelectorAll('iframe')) {
          try {
            const inner = frame.contentDocument
            if (inner) queue.push(inner)
          } catch {
            // cross-origin frame
          }
        }
      }
    }
  }

  const nodes: Array<{ index: number; element: Element; title?: string }> =
    entries ?? gathered.map((element, i) => ({ index: i + 1, element }))

  const view = typeof window !== 'undefined' ? window : undefined
  const viewport = view?.innerHeight ?? 10_000
  const scrollX = view?.scrollX ?? 0
  const scrollY = view?.scrollY ?? 0

  /**
   * The element that encloses a shadow root or a same-origin iframe. Records
   * living in either are ordinary records; only the walk up to them differs.
   */
  function hostOf(node: Element): Element | null {
    const root = node.getRootNode?.() as { host?: Element } | undefined
    if (root?.host) return root.host
    try {
      return (node.ownerDocument?.defaultView?.frameElement as Element | null) ?? null
    } catch {
      return null // cross-origin frame — nothing readable above this point
    }
  }

  function parentOf(node: Element): Element | null {
    return node.parentElement ?? hostOf(node)
  }

  /** True when `selector` matches any ancestor, shadow hosts and frames included. */
  function within(element: Element, selector: string): boolean {
    let node: Element | null = element
    for (let hop = 0; hop < 6 && node; hop += 1) {
      if (node.closest?.(selector)) return true
      node = hostOf(node)
    }
    return false
  }

  /** Distance from an element's own frame to the top document. */
  function frameOffset(element: Element): { x: number; y: number } {
    let x = 0
    let y = 0
    let node = element.ownerDocument?.defaultView?.frameElement as Element | null | undefined
    for (let depth = 0; depth < 4 && node; depth += 1) {
      const rect = node.getBoundingClientRect()
      x += rect.left
      y += rect.top
      try {
        node = node.ownerDocument?.defaultView?.frameElement as Element | null
      } catch {
        break
      }
    }
    return { x, y }
  }

  function signature(element: Element): string {
    const parts: string[] = []
    let node: Element | null = element
    for (let depth = 0; depth < 5 && node && node !== doc?.body; depth += 1) {
      const tag = node.tagName.toLowerCase()
      const classes = (node.getAttribute('class') ?? '')
        .split(/\s+/)
        .filter(Boolean)
        .map((name) => name.replace(/\d+/g, '#'))
        .filter((name) => name.length <= 30)
        .slice(0, 2)
        .join('.')
      parts.unshift(classes ? `${tag}.${classes}` : tag)
      node = parentOf(node)
    }
    return parts.join('>')
  }

  function recordOf(element: Element): Element {
    let card = element
    let node = parentOf(element)
    for (let depth = 0; depth < 4 && node && node !== doc?.body; depth += 1) {
      const tag = node.tagName
      if (tag === 'BODY' || tag === 'HTML' || tag === 'IFRAME') break
      const rect = node.getBoundingClientRect()
      if (rect.width >= 120 && rect.height >= 72) {
        card = node
        if (rect.width >= 180 && rect.height >= 110) break
      }
      node = parentOf(node)
    }
    return card
  }

  const out: Candidate[] = []
  for (const { index, element, title } of nodes) {
    if (typeof element?.getBoundingClientRect !== 'function') continue
    const rect = element.getBoundingClientRect()
    const offset = frameOffset(element)
    const top = rect.top + offset.y
    const left = rect.left + offset.x
    const card = recordOf(element)

    const texts: string[] = []
    const walker = (card.ownerDocument ?? doc)?.createTreeWalker(card, SHOW_TEXT)
    while (walker?.nextNode() && texts.length < 24) {
      const text = (walker.currentNode.nodeValue ?? '').replace(/\s+/g, ' ').trim()
      if (text) texts.push(text.slice(0, 200))
    }
    // Text walking yields nothing for closed shadow roots and detached nodes.
    if (!texts.length) {
      const flat = (card.textContent ?? '').replace(/\s+/g, ' ').trim()
      if (flat) texts.push(flat.slice(0, 200))
    }
    if (title) texts.unshift(title.replace(/\s+/g, ' ').trim().slice(0, 200))

    const linkTexts: string[] = []
    for (const link of card.querySelectorAll?.('a[href]') ?? []) {
      if (link === element || link.contains(element) || element.contains(link)) continue
      const text = (link.textContent ?? '').replace(/\s+/g, ' ').trim()
      if (text) linkTexts.push(text.slice(0, 80))
      if (linkTexts.length >= 4) break
    }

    out.push({
      index,
      tag: element.tagName.toLowerCase(),
      href: element.getAttribute('href') ?? undefined,
      label:
        element.getAttribute('aria-label')?.trim() ||
        element.getAttribute('title')?.trim() ||
        card.querySelector?.('a[title]')?.getAttribute('title')?.trim() ||
        undefined,
      path: signature(element),
      texts,
      linkTexts,
      rect: { top: top + scrollY, left: left + scrollX, width: rect.width, height: rect.height },
      hasMedia: Boolean(card.querySelector?.('img,picture,video,source,[style*="background-image"]')),
      inChrome: within(element, CHROME),
      inBanner: within(element, BANNER),
      visible: rect.width > 0 && rect.height > 0 && top + rect.height > 0 && top < viewport,
    })
  }
  return out
}
