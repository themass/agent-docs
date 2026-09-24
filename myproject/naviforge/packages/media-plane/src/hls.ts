import { parseM3u8Lines } from './hints.js'

export type HlsPlaylistKind = 'master' | 'media' | 'unknown'

export type HlsPlaylistResult = {
  kind: HlsPlaylistKind
  /** Child playlists from a master playlist. */
  variants: string[]
  /** Segment or media URIs from a media playlist. */
  segments: string[]
}

function resolveUrl(line: string, baseUrl?: string): string {
  if (!baseUrl) return line
  try {
    return new URL(line, baseUrl).href
  } catch {
    return line
  }
}

/** Parse m3u8 master/media playlist into variant and segment URL lists (no fetch/decrypt). */
export function resolveHlsPlaylist(text: string, baseUrl?: string): HlsPlaylistResult {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const isMaster = lines.some((line) => line.includes('#EXT-X-STREAM-INF'))
  const variants: string[] = []
  const segments: string[] = []

  for (let index = 0; index < lines.length; index++) {
    const line = lines[index]!
    if (line.startsWith('#')) {
      if (line.includes('#EXT-X-STREAM-INF')) {
        const next = lines[index + 1]
        if (next && !next.startsWith('#')) variants.push(resolveUrl(next, baseUrl))
      }
      continue
    }
    const url = resolveUrl(line, baseUrl)
    if (/\.m3u8(\?|$)/i.test(url)) variants.push(url)
    else segments.push(url)
  }

  const uniqueVariants = [...new Set(variants)]
  const uniqueSegments = [...new Set(segments)]
  const kind: HlsPlaylistKind = isMaster
    ? 'master'
    : uniqueSegments.length
      ? 'media'
      : uniqueVariants.length
        ? 'master'
        : 'unknown'

  return { kind, variants: uniqueVariants, segments: uniqueSegments.slice(0, 512) }
}

/** One-hop resolve: parse playlist text; if master, surface variant URLs only. */
export function resolveHlsFromText(text: string, baseUrl?: string): HlsPlaylistResult {
  const parsed = resolveHlsPlaylist(text, baseUrl)
  if (parsed.kind !== 'master' || !parsed.variants.length) return parsed
  const allSegments: string[] = []
  for (const variant of parsed.variants.slice(0, 3)) {
    allSegments.push(...parseM3u8Lines(text, variant).filter((url) => /\.ts(\?|$)/i.test(url)))
  }
  return {
    kind: 'master',
    variants: parsed.variants,
    segments: [...new Set(allSegments)].slice(0, 512),
  }
}
