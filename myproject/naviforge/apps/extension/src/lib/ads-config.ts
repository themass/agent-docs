/**
 * MV3 extension pages cannot load `pagead2.googlesyndication.com` in script-src.
 * Host thin HTML pages on your server with AdSense; extension embeds them via iframe.
 *
 * Deploy `docs/store-assets/ads/*.html` under this base (e.g. …/file/ads/agent.html).
 */
export const AD_EMBED_BASE_URL = ''

export type AdSurface = 'agent' | 'screenshot' | 'options'

export function adEmbedUrl(surface: AdSurface): string | null {
  const base = AD_EMBED_BASE_URL.trim().replace(/\/$/, '')
  if (!base) return null
  return `${base}/${surface}.html`
}

export function adsEnabled(surface: AdSurface): boolean {
  return adEmbedUrl(surface) != null
}
