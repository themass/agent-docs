import {
  compactReadableText,
  githubRawReadmeUrl,
  pickPreferredReadChars,
  READ_ROOT_SELECTORS,
  stripChromePrefix,
  type PageReadPayload,
} from './read-page-core'

export { compactReadableText, githubRawReadmeUrl, parseGithubRepoPath } from './read-page-core'
export type { PageReadPayload } from './read-page-core'

function visibleText(element: Element | null | undefined): string {
  if (!element || !(element instanceof HTMLElement)) return ''
  return (element.innerText ?? element.textContent ?? '').trim()
}

/** Extract human-readable page text for Q&A / summarize tasks (content-script only). */
export function readVisiblePageContent(doc: Document = document): PageReadPayload {
  const title = doc.title
  const url = doc.location?.href ?? ''
  const body = visibleText(doc.body)
  const candidates: Array<{ source: string; raw: string }> = []
  for (const { selector, source, minChars = 60 } of READ_ROOT_SELECTORS) {
    for (const node of doc.querySelectorAll(selector)) {
      const raw = visibleText(node)
      if (raw.length >= minChars) candidates.push({ source, raw })
    }
  }
  const bestLen = pickPreferredReadChars(
    candidates.map((c) => c.raw.length),
    body.length
  )
  const chosen = candidates.find((c) => c.raw.length === bestLen)
  const raw = chosen?.raw ?? body
  const packed = compactReadableText(stripChromePrefix(raw, title))
  return { ...packed, source: chosen?.source ?? 'body', title, url }
}
