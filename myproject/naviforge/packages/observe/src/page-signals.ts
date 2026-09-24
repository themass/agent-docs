import { mediaHintsFromUrls } from '@naviforge/media-plane'
import type {
  PageSignal,
  PageSignalCollectPayload,
  PageSignalsBundle,
} from '@naviforge/dom-plane/page-signals.js'

export type { PageSignal, PageSignalCollectPayload, PageSignalsBundle }

const URL_LITERAL =
  /https?:\/\/[^\s"'<>\\]+|(?:\/|\.\/)?[a-zA-Z0-9_\-./]+\.(?:m3u8|mp4|webm|mp3|jpg|jpeg|png|gif|webp|avif)(?:\?[^\s"'<>\\]*)?/gi

const MEDIA_EXT = /\.(m3u8|mp4|webm|mp3|jpg|jpeg|png|gif|webp|avif)(\?|$)/i

function str(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined
}

function extractBalancedJson(text: string, start: number): string | null {
  const open = text[start]
  if (open !== '{' && open !== '[') return null
  const close = open === '{' ? '}' : ']'
  let depth = 0
  let inString = false
  let escape = false
  for (let i = start; i < text.length; i++) {
    const c = text[i]!
    if (escape) {
      escape = false
      continue
    }
    if (c === '\\') {
      escape = true
      continue
    }
    if (c === '"') {
      inString = !inString
      continue
    }
    if (inString) continue
    if (c === open) depth++
    if (c === close) {
      depth--
      if (depth === 0) return text.slice(start, i + 1)
    }
  }
  return null
}

function parseJsonLiteral(raw: string): unknown | null {
  try {
    return JSON.parse(raw.replace(/\\\//g, '/')) as unknown
  } catch {
    return null
  }
}

function extractInlineAssignments(script: string): Array<{ name: string; data: unknown }> {
  const out: Array<{ name: string; data: unknown }> = []
  const head = /(?:window\.(\$?[\w.[\]$]+)|var\s+(\w+)|const\s+(\w+)|let\s+(\w+))\s*=\s*/g
  for (const match of script.matchAll(head)) {
    const name = match[1] ?? match[2] ?? match[3] ?? match[4] ?? 'assignment'
    const start = match.index! + match[0].length
    const jsonText = extractBalancedJson(script, start)
    if (!jsonText) continue
    const data = parseJsonLiteral(jsonText)
    if (data != null) out.push({ name, data })
  }
  if (script.includes('application/ld+json')) {
    const ld = script.match(/<script[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/i)
    if (ld?.[1]) {
      const data = parseJsonLiteral(ld[1].trim())
      if (data != null) out.push({ name: 'ld+json', data })
    }
  }
  return out
}

function walkJsonStrings(
  value: unknown,
  path: string,
  visit: (path: string, text: string) => void
): void {
  if (typeof value === 'string') {
    visit(path, value)
    return
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => walkJsonStrings(item, `${path}[${index}]`, visit))
    return
  }
  if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      walkJsonStrings(child, path ? `${path}.${key}` : key, visit)
    }
  }
}

function resolveCdnPlayback(obj: Record<string, unknown>, source: string): PageSignal[] {
  const hls = str(obj.hls ?? obj.url ?? obj.playUrl ?? obj.videoUrl ?? obj.src)
  if (!hls) return []
  // ponytail: skip bare domain noise from CMS globals (e.g. maccms list pages)
  if (!hls.startsWith('http') && !hls.startsWith('/') && !hls.includes('.m3u8') && hls.includes('.')) {
    return []
  }
  const cdns = Array.isArray(obj.cdns)
    ? obj.cdns.filter((x): x is string => typeof x === 'string' && x.trim().length > 0)
    : str(obj.cdn)
      ? [str(obj.cdn)!]
      : []
  const out: PageSignal[] = [
    {
      kind: 'inline_config',
      source,
      label: 'hls',
      value: hls,
      confidence: 0.88,
    },
  ]
  if (hls.startsWith('http')) {
    const isPlayer = /player_/i.test(source) || obj.flag === 'play' || typeof obj.from === 'string'
    out.push({
      kind: 'resolved',
      source,
      label: 'playback',
      value: hls,
      resolvedUrl: hls,
      confidence: isPlayer ? 0.96 : 0.9,
      reason: isPlayer ? 'player config url' : 'absolute media url in config',
    })
    return out
  }
  for (const cdn of cdns.slice(0, 4)) {
    const host = cdn.replace(/^https?:\/\//, '').replace(/\/$/, '')
    const path = hls.startsWith('/') ? hls : `/${hls}`
    const profileBoost = /\$avdt|avdt/i.test(source) ? 0.02 : 0
    out.push({
      kind: 'resolved',
      source,
      label: 'playback',
      value: hls,
      resolvedUrl: `https://${host}${path}`,
      confidence: Math.min(0.98, 0.94 + profileBoost),
      reason: `cdn ${host} + relative path${profileBoost ? ' ($avdt profile)' : ''}`,
    })
  }
  return out
}

function pushUnique(signals: PageSignal[], signal: PageSignal): void {
  const key = `${signal.kind}|${signal.resolvedUrl ?? signal.value}|${signal.label}`
  if (signals.some((s) => `${s.kind}|${s.resolvedUrl ?? s.value}|${s.label}` === key)) return
  signals.push(signal)
}

const PLAYER_MARKERS: Array<{ id: string; pattern: RegExp }> = [
  { id: 'hls.js', pattern: /\bHls\.(?:isSupported|Events)\b/i },
  { id: 'video.js', pattern: /\bvideojs\b/i },
  { id: 'dplayer', pattern: /\bDPlayer\b/i },
  { id: 'artplayer', pattern: /\bArtplayer\b/i },
  { id: 'xgplayer', pattern: /\bxgplayer\b/i },
]

const B64_URL = /atob\s*\(\s*['"]([A-Za-z0-9+/=]{16,})['"]\s*\)/g

function detectPlayerFingerprints(scripts: string[]): PageSignal[] {
  const text = scripts.join('\n').slice(0, 200_000)
  const out: PageSignal[] = []
  for (const { id, pattern } of PLAYER_MARKERS) {
    if (!pattern.test(text)) continue
    out.push({
      kind: 'derived',
      source: 'script:fingerprint',
      label: 'player',
      value: id,
      confidence: 0.72,
      reason: 'player library marker in page scripts',
    })
  }
  return out
}

function decodeObfuscatedUrls(text: string, source: string): PageSignal[] {
  const out: PageSignal[] = []
  for (const match of text.matchAll(B64_URL)) {
    try {
      const decoded = atob(match[1]!)
      if (!/^https?:\/\//.test(decoded) && !MEDIA_EXT.test(decoded)) continue
      out.push({
        kind: 'derived',
        source,
        label: 'b64_url',
        value: decoded,
        resolvedUrl: decoded.startsWith('http') ? decoded : undefined,
        confidence: 0.75,
        reason: 'atob() decoded from script',
      })
    } catch {
      /* skip invalid b64 */
    }
  }
  return out
}

function mineExternalScriptBodies(
  bodies: Array<{ url: string; preview: string }>,
  pageUrl: string
): PageSignal[] {
  const out: PageSignal[] = []
  for (const { url, preview } of bodies) {
    const source = `script:external:${url}`
    for (const { name, data } of extractInlineAssignments(preview)) {
      const src = `${source} ${name}`
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        for (const s of resolveCdnPlayback(data as Record<string, unknown>, src)) {
          pushUnique(out, s)
        }
      }
      walkJsonStrings(data, name, (path, text) => {
        if (!MEDIA_EXT.test(text) && !text.includes('/api/') && !text.startsWith('http')) return
        pushUnique(out, {
          kind: 'inline_config',
          source: `${src}.${path}`,
          label: path.split('.').pop() ?? path,
          value: text,
          confidence: 0.8,
          resolvedUrl: text.startsWith('http') ? text : undefined,
        })
      })
    }
    for (const match of preview.matchAll(URL_LITERAL)) {
      const lit = match[0]!
      let resolved: string | undefined
      try {
        resolved = new URL(lit, pageUrl).href
      } catch {
        resolved = lit.startsWith('http') ? lit : undefined
      }
      pushUnique(out, {
        kind: 'url_literal',
        source,
        label: 'bundle_url',
        value: lit,
        resolvedUrl: resolved,
        confidence: MEDIA_EXT.test(lit) ? 0.78 : 0.68,
      })
    }
    for (const s of decodeObfuscatedUrls(preview, source)) pushUnique(out, s)
  }
  return out
}

/** Deterministic miner: inline scripts, DOM resources, meta, optional network URLs. */
export function minePageSignals(
  raw: PageSignalCollectPayload,
  opts?: {
    networkUrls?: string[]
    scriptBodies?: Array<{ url: string; preview: string }>
  }
): PageSignalsBundle {
  const signals: PageSignal[] = []
  const pageUrl = raw.url

  raw.inlineScripts.forEach((script, index) => {
    const source = `script:inline:${index}`
    for (const { name, data } of extractInlineAssignments(script)) {
      const src = `${source} ${name}`
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        for (const s of resolveCdnPlayback(data as Record<string, unknown>, src)) {
          pushUnique(signals, s)
        }
      }
      walkJsonStrings(data, name, (path, text) => {
        if (!MEDIA_EXT.test(text) && !text.includes('/api/') && !text.startsWith('http')) return
        pushUnique(signals, {
          kind: 'inline_config',
          source: `${src}.${path}`,
          label: path.split('.').pop() ?? path,
          value: text,
          confidence: MEDIA_EXT.test(text) ? 0.82 : 0.7,
        })
        if (text.startsWith('http') && MEDIA_EXT.test(text)) {
          pushUnique(signals, {
            kind: 'url_literal',
            source: `${src}.${path}`,
            label: path,
            value: text,
            resolvedUrl: text,
            confidence: 0.84,
          })
          pushUnique(signals, {
            kind: 'resolved',
            source: `${src}.${path}`,
            label: 'playback',
            value: text,
            resolvedUrl: text,
            confidence: /player_/i.test(src) || path === 'url' ? 0.95 : 0.88,
            reason: 'inline json media url',
          })
        } else if (text.startsWith('http')) {
          pushUnique(signals, {
            kind: 'url_literal',
            source: `${src}.${path}`,
            label: path,
            value: text,
            resolvedUrl: text,
            confidence: 0.84,
          })
        }
      })
    }
    for (const match of script.matchAll(URL_LITERAL)) {
      const url = match[0]!
      pushUnique(signals, {
        kind: 'url_literal',
        source,
        label: 'script_url',
        value: url,
        resolvedUrl: url.startsWith('http') ? url : undefined,
        confidence: MEDIA_EXT.test(url) ? 0.8 : 0.65,
      })
    }
    for (const s of decodeObfuscatedUrls(script, source)) pushUnique(signals, s)
  })

  for (const s of detectPlayerFingerprints(raw.inlineScripts)) pushUnique(signals, s)

  for (const [index, script] of (raw.iframeInlineScripts ?? []).entries()) {
    const source = `script:iframe:${index}`
    for (const { name, data } of extractInlineAssignments(script)) {
      const src = `${source} ${name}`
      if (data && typeof data === 'object' && !Array.isArray(data)) {
        for (const s of resolveCdnPlayback(data as Record<string, unknown>, src)) {
          pushUnique(signals, s)
        }
      }
    }
    for (const s of decodeObfuscatedUrls(script, source)) pushUnique(signals, s)
  }

  const scriptBodySources = [
    ...(opts?.scriptBodies ?? []),
    ...(raw.fetchedScriptBodies ?? []),
  ]
  if (scriptBodySources.length) {
    for (const s of mineExternalScriptBodies(scriptBodySources, pageUrl)) pushUnique(signals, s)
  }

  for (const src of raw.externalScriptSrcs) {
    pushUnique(signals, {
      kind: 'url_literal',
      source: 'script:external',
      label: 'script_src',
      value: src,
      resolvedUrl: src,
      confidence: 0.55,
    })
  }

  for (const item of raw.meta) {
    const key = item.property ?? item.name ?? 'meta'
    if (!item.content) continue
    const isMedia = /image|video|url/i.test(key) || MEDIA_EXT.test(item.content)
    pushUnique(signals, {
      kind: 'meta',
      source: `meta:${key}`,
      label: key,
      value: item.content,
      resolvedUrl: item.content.startsWith('http') ? item.content : undefined,
      confidence: isMedia ? 0.78 : 0.6,
    })
  }

  for (const res of raw.resources) {
    if (/\.gif(\?|$)/i.test(res.value)) continue
    let resolved = res.value
    try {
      resolved = new URL(res.value, pageUrl).href
    } catch {
      /* keep raw */
    }
    pushUnique(signals, {
      kind: 'dom_resource',
      source: `${res.tag}[${res.attr}]`,
      label: res.attr,
      value: res.value,
      resolvedUrl: resolved.startsWith('http') ? resolved : undefined,
      confidence: MEDIA_EXT.test(res.value) ? 0.76 : 0.62,
    })
  }

  for (const style of raw.styleResources ?? []) {
    let resolved = style.value
    try {
      resolved = new URL(style.value, pageUrl).href
    } catch {
      /* keep raw */
    }
    pushUnique(signals, {
      kind: 'style',
      source: `${style.tag}[${style.property}]`,
      label: style.property,
      value: style.value,
      resolvedUrl: resolved.startsWith('http') ? resolved : undefined,
      confidence: MEDIA_EXT.test(style.value) ? 0.74 : 0.64,
      reason: 'CSS background-image',
    })
  }

  for (const url of opts?.networkUrls ?? []) {
    for (const hint of mediaHintsFromUrls([{ url }])) {
      pushUnique(signals, {
        kind: 'network',
        source: 'network:session',
        label: hint.kind,
        value: hint.url,
        resolvedUrl: hint.url,
        confidence: hint.kind === 'hls' ? 0.92 : 0.86,
        reason: hint.kind === 'hls' ? 'network m3u8 (incl. proxy ?url=)' : undefined,
      })
      if (hint.kind === 'hls') {
        pushUnique(signals, {
          kind: 'resolved',
          source: 'network:session',
          label: 'playback',
          value: hint.url,
          resolvedUrl: hint.url,
          confidence: 0.91,
          reason: 'network m3u8 request',
        })
      }
    }
  }

  signals.sort((a, b) => b.confidence - a.confidence)
  return { url: pageUrl, signals: signals.slice(0, 32) }
}

export function formatPageSignalsForPrompt(bundle: PageSignalsBundle, maxChars = 4_800): string {
  if (!bundle.signals.length) {
    return `PAGE SIGNALS (${bundle.url})\n(none — no inline config, media URLs, or network hints found)`
  }
  const lines = bundle.signals.slice(0, 20).map((s) => {
    const url = s.resolvedUrl ? ` → ${s.resolvedUrl}` : ''
    const why = s.reason ? ` (${s.reason})` : ''
    return `- [${s.kind}] ${s.label}: ${s.value}${url}${why}  @{${s.source}}`
  })
  let text = `PAGE SIGNALS (${bundle.url})\n${lines.join('\n')}`
  if (text.length > maxChars) text = `${text.slice(0, maxChars)}\n… (truncated)`
  return text
}
