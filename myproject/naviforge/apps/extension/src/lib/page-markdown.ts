import { Readability } from '@mozilla/readability'
import TurndownService from 'turndown'

/** Cap HTML fed to Turndown so a media-heavy article cannot balloon the file. */
const MAX_HTML_CHARS = 2_000_000

export type PageMarkdownResult = {
  markdown: string
  title: string
  url: string
  source: 'readability' | 'html'
}

function Turndown(): typeof TurndownService {
  const mod = TurndownService as unknown as { default?: typeof TurndownService }
  return mod.default ?? TurndownService
}

/** HTML → Markdown via Turndown (works in the content script and in Node). */
export function htmlToMarkdown(html: string): string {
  const turndown = new (Turndown())({
    headingStyle: 'atx',
    codeBlockStyle: 'fenced',
    bulletListMarker: '-',
  })
  turndown.remove(['script', 'style', 'noscript', 'iframe'])
  turndown.addRule('skipEmbeddedImages', {
    filter: (node) =>
      node.nodeName === 'IMG' && /^(data:|blob:)/i.test(node.getAttribute('src') ?? ''),
    replacement: () => '',
  })
  return turndown.turndown(html).trim()
}

export function wrapPageMarkdown(title: string, url: string, body: string): string {
  const heading = title.trim() || 'Untitled'
  const source = url.trim()
  return `# ${heading}\n\n${source ? `Source: ${source}\n\n` : ''}${body.trim()}\n`
}

function pickExportHtml(doc: Document): string {
  const root = doc.querySelector('article, [role="main"], main, .markdown-body, .theme-doc-markdown')
  if (root instanceof HTMLElement && root.innerHTML.trim()) return root.innerHTML
  return doc.body?.innerHTML ?? ''
}

/** Readability article HTML → Markdown. Falls back to main/article/body HTML. */
export function pageDocumentToMarkdown(doc: Document): PageMarkdownResult {
  const url = doc.location?.href ?? ''
  const fallbackTitle = doc.title.trim() || 'Untitled'
  let html = ''
  let title = fallbackTitle
  let source: PageMarkdownResult['source'] = 'html'

  try {
    const parsed = new Readability(doc.cloneNode(true) as Document).parse()
    if (parsed?.content) {
      html = parsed.content
      title = parsed.title?.trim() || fallbackTitle
      source = 'readability'
    }
  } catch {
    // clone/parse failed; use raw HTML
  }

  if (!html.trim()) {
    html = pickExportHtml(doc)
    source = 'html'
  }
  if (!html.trim()) throw new Error('no readable HTML on this page — try page.to_pdf')

  const body = htmlToMarkdown(html.slice(0, MAX_HTML_CHARS))
  if (!body) throw new Error('markdown conversion produced empty output')
  return { markdown: wrapPageMarkdown(title, url, body), title, url, source }
}
