import type { AgentCtx } from '../agent-ctx.js'
import type { DomPlane } from '@naviforge/dom-plane'
import type { PageSignalsBundle } from '@naviforge/observe'
import { hydratePageSignals } from '../page-signals-hydrate.js'
import {
  classifyPlaybackUrl,
  isLikelyPlayPageUrl,
  type MediaPlaybackFormat,
} from './media-entry.js'
import { throttleCatalogNav } from './throttle.js'

/** Find play/watch/detail-next hop on same origin (Phase 3 multi-hop). */
export const RESOLVE_DETAIL_LINK_JS = `(() => {
  const origin = location.origin
  const clean = (s) => (s || '').trim()
  const playLabel = /播放|play|watch|立即|在线|观看|stream|点播|全集/i
  const pathHint = /\\/(play|video|watch|stream|player|vodplay|embed)\\//i
  const links = [...document.querySelectorAll('a[href]')]
  const scored = []
  for (const a of links) {
    if (!a.href.startsWith(origin)) continue
    const t = clean(a.textContent)
    let score = 0
    if (playLabel.test(t)) score += 3
    try {
      if (pathHint.test(new URL(a.href).pathname)) score += 4
    } catch {}
    if (a.className && /play|btn-play|video/i.test(String(a.className))) score += 2
    if (score > 0) scored.push({ href: a.href, score })
  }
  scored.sort((a, b) => b.score - a.score)
  return scored[0]?.href ?? null
})()`

const DEFAULT_MAX_HOPS = 2

export type MediaResolveResult = {
  mediaUrl?: string
  playPageUrl?: string
  format?: MediaPlaybackFormat
  confidence?: number
  shortfall?: string
  hops: string[]
}

function pickBestPlayback(bundle: PageSignalsBundle): {
  url: string
  confidence: number
  format: MediaPlaybackFormat
} | null {
  const candidates = bundle.signals
    .filter((s) => s.kind === 'resolved' && s.resolvedUrl && (s.confidence ?? 0) >= 0.85)
    .sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0))
  const top = candidates[0]
  if (!top?.resolvedUrl) return null
  return {
    url: top.resolvedUrl,
    confidence: top.confidence ?? 0.88,
    format: classifyPlaybackUrl(top.resolvedUrl),
  }
}

function hasEmbedPlayer(bundle: PageSignalsBundle): boolean {
  return bundle.signals.some(
    (s) =>
      /video|iframe|player|embed/i.test(s.source) ||
      /video\.js|dplayer|plyr|jwplayer/i.test(s.value ?? '')
  )
}

async function readDetailLink(dom: DomPlane): Promise<string | null> {
  if (!dom.executeJs) return null
  const ran = await dom.executeJs({ code: RESOLVE_DETAIL_LINK_JS })
  if (!ran.ok) return null
  const href = (ran.data as { result?: unknown }).result
  return typeof href === 'string' && href.startsWith('http') ? href : null
}

/** Navigate up to maxHops pages; extract direct stream or play/embed page. */
export async function resolveMediaWithHops(
  ctx: AgentCtx,
  dom: DomPlane,
  startUrl: string,
  maxHops = DEFAULT_MAX_HOPS
): Promise<MediaResolveResult> {
  const hops: string[] = []
  let current = startUrl
  let lastBundle: PageSignalsBundle | null = null

  for (let hop = 0; hop < maxHops; hop++) {
    await throttleCatalogNav()
    if (!dom.navigate) break
    const nav = await dom.navigate('url', current)
    if (!nav.ok) break
    hops.push(current)
    if (dom.wait) await dom.wait({ kind: 'stable', timeoutMs: hop === 0 ? 600 : 800 })

    const { bundle } = await hydratePageSignals({
      dom,
      network: ctx.agent.planes.network,
      url: current,
    })
    lastBundle = bundle

    const best = pickBestPlayback(bundle)
    if (best) {
      return {
        mediaUrl: best.url,
        format: best.format,
        confidence: best.confidence,
        hops,
      }
    }

    if (hop >= maxHops - 1) break
    const next = await readDetailLink(dom)
    if (!next || next === current) break
    current = next
  }

  const lastHop = hops[hops.length - 1] ?? startUrl
  if (isLikelyPlayPageUrl(lastHop) || hasEmbedPlayer(lastBundle ?? { url: lastHop, signals: [] })) {
    return {
      playPageUrl: lastHop,
      format: 'embed',
      confidence: 0.55,
      shortfall: 'no direct stream in PAGE SIGNALS — embed/play page; agent may click play or spawn',
      hops,
    }
  }

  return {
    shortfall: hops.length ? 'visited detail but no playback signal' : 'navigation failed',
    hops,
  }
}
