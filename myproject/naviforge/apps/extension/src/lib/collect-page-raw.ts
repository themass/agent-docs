import type { PageSignalCollectPayload } from '@naviforge/dom-plane/page-signals.js'

const MAX_SCRIPT = 80_000

function absUrl(value: string, base: string): string {
  try {
    return new URL(value, base).href
  } catch {
    return value
  }
}

/** Collect raw page artifacts for signal mining (content-script world). */
export function collectPageSignalRaw(doc: Document, pageUrl: string): PageSignalCollectPayload {
  const inlineScripts: string[] = []
  const externalScriptSrcs: string[] = []
  for (const el of doc.querySelectorAll('script')) {
    const src = el.getAttribute('src')
    if (src) {
      externalScriptSrcs.push(absUrl(src, pageUrl))
      continue
    }
    const text = el.textContent?.trim()
    if (text) inlineScripts.push(text.slice(0, MAX_SCRIPT))
  }

  const meta = [...doc.querySelectorAll('meta')]
    .map((el) => ({
      name: el.getAttribute('name') ?? undefined,
      property: el.getAttribute('property') ?? undefined,
      content: el.getAttribute('content') ?? '',
    }))
    .filter((m) => m.content.trim())

  const resources: PageSignalCollectPayload['resources'] = []
  const pushRes = (el: Element, attr: string) => {
    const value = el.getAttribute(attr)
    if (!value?.trim()) return
    resources.push({ tag: el.tagName.toLowerCase(), attr, value: value.trim() })
  }
  for (const img of doc.querySelectorAll('img')) {
    pushRes(img, 'src')
    pushRes(img, 'data-src')
    pushRes(img, 'data-original')
  }
  for (const video of doc.querySelectorAll('video')) {
    pushRes(video, 'src')
    pushRes(video, 'poster')
  }
  for (const source of doc.querySelectorAll('video source, audio source')) {
    pushRes(source, 'src')
  }
  for (const link of doc.querySelectorAll('link[href]')) {
    const rel = (link.getAttribute('rel') ?? '').toLowerCase()
    if (rel.includes('stylesheet') || rel.includes('preload') || rel.includes('icon')) {
      pushRes(link, 'href')
    }
  }

  return {
    url: pageUrl,
    title: doc.title,
    inlineScripts,
    externalScriptSrcs,
    meta,
    resources,
    styleResources: collectStyleResources(doc, pageUrl),
  }
}

const BG_URL = /url\(\s*['"]?([^'")]+)['"]?\s*\)/gi

function collectStyleResources(
  doc: Document,
  pageUrl: string
): NonNullable<PageSignalCollectPayload['styleResources']> {
  const out: NonNullable<PageSignalCollectPayload['styleResources']> = []
  const seen = new Set<string>()
  const scan = (el: Element) => {
    const inline = el.getAttribute('style')
    if (inline) {
      for (const match of inline.matchAll(BG_URL)) {
        const raw = match[1]?.trim()
        if (!raw || raw.startsWith('data:')) continue
        const value = absUrl(raw, pageUrl)
        const key = `style|${value}`
        if (seen.has(key)) continue
        seen.add(key)
        out.push({ tag: el.tagName.toLowerCase(), property: 'background-image', value })
      }
    }
    try {
      const computed = doc.defaultView?.getComputedStyle(el)
      const bg = computed?.backgroundImage
      if (bg && bg !== 'none') {
        for (const match of bg.matchAll(BG_URL)) {
          const raw = match[1]?.trim()
          if (!raw || raw.startsWith('data:')) continue
          const value = absUrl(raw, pageUrl)
          const key = `computed|${value}`
          if (seen.has(key)) continue
          seen.add(key)
          out.push({ tag: el.tagName.toLowerCase(), property: 'background-image(computed)', value })
        }
      }
    } catch {
      /* cross-origin stylesheet access */
    }
  }
  const nodes = doc.querySelectorAll('[style*="background"], img, video, div, section, figure')
  let n = 0
  for (const el of nodes) {
    scan(el)
    if (++n >= 48) break
  }
  return out.slice(0, 24)
}

/** F3: same-origin iframe inline scripts (cross-origin iframes are skipped). */
function collectSameOriginIframeScripts(doc: Document): string[] {
  const out: string[] = []
  for (const iframe of doc.querySelectorAll('iframe')) {
    try {
      const idoc = iframe.contentDocument
      if (!idoc) continue
      for (const el of idoc.querySelectorAll('script')) {
        const src = el.getAttribute('src')
        if (src) continue
        const text = el.textContent?.trim()
        if (text) out.push(text.slice(0, MAX_SCRIPT))
      }
    } catch {
      /* cross-origin */
    }
  }
  return out.slice(0, 8)
}

const MAX_FETCH_SCRIPT = 12_000
const MAX_FETCH_SCRIPTS = 3

/** F2: fetch same-origin external scripts when credentials allow. */
async function fetchSameOriginScriptBodies(
  srcs: string[],
  pageUrl: string
): Promise<Array<{ url: string; preview: string }>> {
  let origin: string
  try {
    origin = new URL(pageUrl).origin
  } catch {
    return []
  }
  const out: Array<{ url: string; preview: string }> = []
  for (const src of srcs) {
    if (out.length >= MAX_FETCH_SCRIPTS) break
    try {
      const url = new URL(src, pageUrl)
      if (url.origin !== origin) continue
      if (!/javascript|\.js(?:\?|$)/i.test(url.pathname + url.search)) continue
      const res = await fetch(url.href, { credentials: 'include', cache: 'force-cache' })
      if (!res.ok) continue
      const text = (await res.text()).slice(0, MAX_FETCH_SCRIPT)
      if (text.trim()) out.push({ url: url.href, preview: text })
    } catch {
      /* CORS or blocked */
    }
  }
  return out
}

/** Async collector: base DOM artifacts + F2/F3 enrichments. */
export async function collectPageSignalRawAsync(
  doc: Document,
  pageUrl: string
): Promise<PageSignalCollectPayload> {
  const base = collectPageSignalRaw(doc, pageUrl)
  const [fetchedScriptBodies, iframeInlineScripts] = await Promise.all([
    fetchSameOriginScriptBodies(base.externalScriptSrcs, pageUrl),
    Promise.resolve(collectSameOriginIframeScripts(doc)),
  ])
  return { ...base, fetchedScriptBodies, iframeInlineScripts }
}
