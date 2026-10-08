import type { AgentCtx } from '../agent-ctx.js';
import type { DomPlane } from '@naviforge/dom-plane';
import { type MediaPlaybackFormat } from './media-entry.js';
/** Find play/watch/detail-next hop on same origin (Phase 3 multi-hop). */
export declare const RESOLVE_DETAIL_LINK_JS = "(() => {\n  const origin = location.origin\n  const clean = (s) => (s || '').trim()\n  const playLabel = /\u64AD\u653E|play|watch|\u7ACB\u5373|\u5728\u7EBF|\u89C2\u770B|stream|\u70B9\u64AD|\u5168\u96C6/i\n  const pathHint = /\\/(play|video|watch|stream|player|vodplay|embed)\\//i\n  const links = [...document.querySelectorAll('a[href]')]\n  const scored = []\n  for (const a of links) {\n    if (!a.href.startsWith(origin)) continue\n    const t = clean(a.textContent)\n    let score = 0\n    if (playLabel.test(t)) score += 3\n    try {\n      if (pathHint.test(new URL(a.href).pathname)) score += 4\n    } catch {}\n    if (a.className && /play|btn-play|video/i.test(String(a.className))) score += 2\n    if (score > 0) scored.push({ href: a.href, score })\n  }\n  scored.sort((a, b) => b.score - a.score)\n  return scored[0]?.href ?? null\n})()";
export type MediaResolveResult = {
    mediaUrl?: string;
    playPageUrl?: string;
    format?: MediaPlaybackFormat;
    confidence?: number;
    shortfall?: string;
    hops: string[];
};
/** Navigate up to maxHops pages; extract direct stream or play/embed page. */
export declare function resolveMediaWithHops(ctx: AgentCtx, dom: DomPlane, startUrl: string, maxHops?: number): Promise<MediaResolveResult>;
