/** Max readable text returned to the model (chars). */
export const PAGE_READ_MAX_CHARS = 24_000

export type PageReadPayload = {
  text: string
  source: string
  truncated: boolean
  title: string
  url: string
}

/** Ordered roots for readable page text. Prefer nested article over wrapping `main`. */
export const READ_ROOT_SELECTORS: ReadonlyArray<{ selector: string; source: string; minChars?: number }> = [
  { selector: 'article.markdown-body', source: 'github-readme', minChars: 40 },
  { selector: '#readme article', source: 'github-readme', minChars: 40 },
  { selector: '[data-testid="about-repo"]', source: 'github-about', minChars: 20 },
  { selector: '.theme-doc-markdown', source: 'docusaurus', minChars: 80 },
  { selector: '.md-content', source: 'mkdocs', minChars: 80 },
  { selector: '.markdown-body', source: 'markdown-body', minChars: 40 },
  { selector: '.doc-content, .docs-content, .doc-body', source: 'doc-content', minChars: 80 },
  { selector: '[class*="article-content"], [class*="articleContent"]', source: 'article-content', minChars: 80 },
  { selector: 'article', source: 'article', minChars: 80 },
  { selector: '[role="main"]', source: 'main', minChars: 120 },
  { selector: 'main', source: 'main', minChars: 120 },
]

/** Title tab → likely H1 (`模型列表--豆包语音-火山引擎` → `模型列表`). */
export function pageHeadingFromTitle(title: string): string {
  return title.split(/\s*(?:—|--|\||·)\s*/)[0]?.trim() || title.trim()
}

/**
 * Drop chrome (account menu, sidebar) that sits before the last copy of the page heading.
 * Last match is usually the article H1 after nav repeats the same label.
 */
export function stripChromePrefix(text: string, title: string): string {
  const heading = pageHeadingFromTitle(title)
  if (heading.length < 2) return text
  let last = -1
  let from = 0
  while (from < text.length) {
    const index = text.indexOf(heading, from)
    if (index < 0) break
    last = index
    from = index + heading.length
  }
  if (last <= 0) return text
  return text.slice(last).trim()
}

/**
 * Prefer a nested article over wrapping `main`/`body`. Tiny widgets lose to the longest root.
 */
export function pickPreferredReadChars(candidates: number[], bodyChars: number): number {
  if (!candidates.length) return 0
  const longest = Math.max(...candidates)
  const cap = Math.max(400, bodyChars * 0.85)
  const nested = candidates.filter((n) => n < cap && n >= Math.min(400, longest * 0.25))
  return nested.length ? Math.max(...nested) : longest
}

export function compactReadableText(text: string, maxChars = PAGE_READ_MAX_CHARS): { text: string; truncated: boolean } {
  const normalized = text.replace(/\r\n/g, '\n').replace(/[ \t]+\n/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
  if (normalized.length <= maxChars) return { text: normalized, truncated: false }
  return { text: `${normalized.slice(0, maxChars)}\n… (truncated)`, truncated: true }
}

/** Full-page interactive snapshots do not shift when the viewport scrolls. */
export function isFullPageSnapshotHeader(header: string): boolean {
  return /\(full page\)/i.test(header)
}

export function snapshotTruncationHint(header: string): string {
  return isFullPageSnapshotHeader(header)
    ? 'use dom.read_page for article/README text, or dom.scroll then dom.snapshot (viewport)'
    : 'use dom.scroll then dom.snapshot'
}

export function parseGithubRepoPath(pathname: string): { owner: string; repo: string } | null {
  const match = /^\/([^/]+)\/([^/]+)\/?$/.exec(pathname)
  if (!match) return null
  const owner = match[1]!
  const repo = match[2]!.replace(/\.git$/i, '')
  if (/^(trending|explore|features|login|signup|settings)$/i.test(owner)) return null
  return { owner, repo }
}

export function githubRawReadmeUrl(pageUrl: string): string | undefined {
  try {
    const parsed = new URL(pageUrl)
    if (!parsed.hostname.endsWith('github.com')) return undefined
    const repo = parseGithubRepoPath(parsed.pathname)
    if (!repo) return undefined
    return `https://raw.githubusercontent.com/${repo.owner}/${repo.repo}/HEAD/README.md`
  } catch {
    return undefined
  }
}
