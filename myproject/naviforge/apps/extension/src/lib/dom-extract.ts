import type { DomExtractItem, DomExtractResult } from '@naviforge/dom-plane'

import { collectCandidates, extractContent } from './content-extract.js'
import { titleForElement } from './feed-mark.js'

export type { DomExtractItem, DomExtractResult }

const INTERACTIVE =
  'a[href],button,input,textarea,select,[role="button"],[role="link"],h1,h2,h3,h4'

function kindFor(element: Element): DomExtractItem['kind'] {
  const tag = element.tagName.toLowerCase()
  if (tag === 'a') return 'link'
  if (tag === 'button' || element.getAttribute('role') === 'button') return 'button'
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return 'input'
  if (/^h[1-4]$/.test(tag)) return 'heading'
  if (element.getAttribute('role') === 'link') return 'link'
  return 'other'
}

function hrefFor(element: Element): string | undefined {
  if (element.tagName.toLowerCase() === 'a') {
    const href = (element as HTMLAnchorElement).href || element.getAttribute('href')
    if (href?.startsWith('http')) return href
  }
  const href = element.getAttribute('href')
  if (href?.startsWith('http')) return href
  return undefined
}

function visible(element: Element): boolean {
  if (typeof element.getBoundingClientRect !== 'function') return false
  const rect = element.getBoundingClientRect()
  const viewport = typeof window !== 'undefined' ? window.innerHeight : 10_000
  return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < viewport
}

export function extractDomFromEntries(
  entries: Array<{ index: number; element: Element }>,
  opts: { url: string; title: string; limit?: number; kind?: 'all' | 'links' | 'buttons' | 'feeds' }
): DomExtractResult {
  const limit = Math.min(96, Math.max(1, opts.limit ?? 48))
  const items: DomExtractItem[] = []

  for (const { index, element } of entries) {
    if (!visible(element)) continue
    const title = titleForElement(element).trim()
    if (!title || title.length < 2) continue
    const kind = kindFor(element)
    if (opts.kind === 'links' && kind !== 'link') continue
    if (opts.kind === 'buttons' && kind !== 'button') continue
    items.push({
      index,
      kind,
      title,
      href: hrefFor(element),
      tag: element.tagName.toLowerCase(),
    })
    if (items.length >= limit) break
  }

  const byIndex = new Map(entries.map((entry) => [entry.index, entry.element]))
  const report = extractContent(collectCandidates(entries), {
    url: opts.url,
    n: Math.min(limit, 24),
  })
  const feeds = report.items.map((item) => ({
    index: item.index,
    kind: 'feed' as const,
    title: item.title,
    href: item.url,
    tag: byIndex.get(item.index)?.tagName.toLowerCase() ?? 'a',
  }))

  const links = items.filter((item) => item.kind === 'link')
  const buttons = items.filter((item) => item.kind === 'button')

  if (opts.kind === 'feeds') {
    return { url: opts.url, title: opts.title, items: feeds, links: [], buttons: [], feeds }
  }

  return {
    url: opts.url,
    title: opts.title,
    items: opts.kind === 'all' ? [...items, ...feeds.filter((f) => !items.some((i) => i.index === f.index))].slice(0, limit) : items,
    links,
    buttons,
    feeds,
  }
}

/** Fallback when selector map is unavailable — scan visible interactive nodes. */
export function extractDomFromDocument(
  opts: { url: string; title: string; limit?: number; kind?: 'all' | 'links' | 'buttons' | 'feeds' }
): DomExtractResult {
  const nodes = [...document.querySelectorAll(INTERACTIVE)]
  const entries = nodes.map((element, index) => ({ index: index + 1, element }))
  return extractDomFromEntries(entries, opts)
}
