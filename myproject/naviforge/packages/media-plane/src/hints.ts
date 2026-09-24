const MEDIA_URL =
  /\.(m3u8|mpd|mp4|webm|m4v)(\?|$)|m3u8|\.ts\b|video\/|application\/vnd\.apple\.mpegurl/i

export type MediaHint = {
  url: string
  kind: 'hls' | 'dash' | 'mp4' | 'segment' | 'other'
  method?: string
  status?: number
}

export function classifyMediaUrl(url: string): MediaHint['kind'] {
  if (/\.m3u8|mpegurl/i.test(url)) return 'hls'
  if (/\.mpd/i.test(url)) return 'dash'
  if (/\.mp4|\.webm|\.m4v/i.test(url)) return 'mp4'
  if (/\.ts(\?|$)/i.test(url)) return 'segment'
  return 'other'
}

/** Proxy players often request `?url=https://…/index.m3u8` — extract nested targets. */
export function expandMediaRequestUrls(url: string): string[] {
  const out: string[] = []
  const push = (candidate: string) => {
    const value = candidate.trim()
    if (!value) return
    if (MEDIA_URL.test(value) || /^https?:\/\/.+\.(m3u8|mp4|mpd|webm)/i.test(value)) {
      if (!out.includes(value)) out.push(value)
    }
  }
  push(url)
  try {
    const parsed = new URL(url)
    for (const value of parsed.searchParams.values()) {
      push(decodeURIComponent(value))
    }
  } catch {
    /* ignore malformed */
  }
  return out
}

export function mediaHintsFromUrls(
  items: Array<{ url: string; method?: string; status?: number }>
): MediaHint[] {
  const seen = new Set<string>()
  const hints: MediaHint[] = []
  for (const item of items) {
    for (const candidate of expandMediaRequestUrls(item.url)) {
      if (!MEDIA_URL.test(candidate)) continue
      const key = candidate.split('?')[0] ?? candidate
      if (seen.has(key)) continue
      seen.add(key)
      hints.push({
        url: candidate,
        kind: classifyMediaUrl(candidate),
        method: item.method,
        status: item.status,
      })
    }
  }
  return hints.slice(0, 24)
}

export function formatMediaHints(hints: MediaHint[]): string {
  if (!hints.length) return 'MEDIA: (none)'
  return [
    `MEDIA hints (${hints.length}):`,
    ...hints.map((hint) => `- ${hint.kind} ${hint.status ?? '-'} ${hint.url.slice(0, 200)}`),
  ].join('\n')
}

/** Parse master/media playlist URIs from m3u8 text (no decryption). */
export function parseM3u8Lines(text: string, baseUrl?: string): string[] {
  const lines = text.split('\n').map((line) => line.trim()).filter(Boolean)
  const urls: string[] = []
  for (const line of lines) {
    if (line.startsWith('#')) continue
    try {
      urls.push(baseUrl ? new URL(line, baseUrl).href : line)
    } catch {
      urls.push(line)
    }
  }
  return urls.slice(0, 48)
}

export function pickMasterPlaylist(hints: MediaHint[]): MediaHint | undefined {
  return hints.find((hint) => hint.kind === 'hls' && !hint.url.includes('.ts'))
}
