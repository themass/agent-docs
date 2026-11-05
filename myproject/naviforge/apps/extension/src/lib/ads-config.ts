/**
 * Google AdSense only (hosted iframe pages — see docs/store-assets/ads/AD_SLOTS.md).
 *
 * Leave empty until HTML + AdSense units are live. Then set base and rebuild.
 * Example: `http://file.ok123find.top/file/ads`
 */
export const AD_EMBED_BASE_URL = ''

/** One AdSense display unit per row (unique data-ad-slot in the matching HTML file). */
export const AD_SLOT_CATALOG = [
  {
    id: 'NVF-ADS-01',
    surface: 'agentFeed',
    html: 'agent-feed.html',
    label: '侧栏 Agent · 对话流 / 空状态',
  },
  {
    id: 'NVF-ADS-02',
    surface: 'agentThinking',
    html: 'agent-thinking.html',
    label: '侧栏 Agent · Thinking 条下方',
  },
  {
    id: 'NVF-ADS-03',
    surface: 'screenshot',
    html: 'screenshot.html',
    label: '截图工作室',
  },
  {
    id: 'NVF-ADS-04',
    surface: 'options',
    html: 'options.html',
    label: '设置控制台顶栏',
  },
  {
    id: 'NVF-ADS-05',
    surface: 'ocr',
    html: 'ocr.html',
    label: 'ToolKit 工具区（含 OCR 入口）',
  },
] as const

export type AdSurface = (typeof AD_SLOT_CATALOG)[number]['surface']

const SURFACE_HTML: Record<AdSurface, string> = {
  agentFeed: 'agent-feed.html',
  agentThinking: 'agent-thinking.html',
  screenshot: 'screenshot.html',
  options: 'options.html',
  ocr: 'ocr.html',
}

/**
 * Surfaces rendered once `AD_EMBED_BASE_URL` is set.
 * Wave 1: settings, toolkit, screenshot. Add `agentFeed` for the empty-state
 * slot only. Leave `agentThinking` out — in-run ads stay off.
 */
export const AD_ENABLED_SURFACES: readonly AdSurface[] = ['options', 'ocr', 'screenshot']

export function adEmbedUrl(surface: AdSurface): string | null {
  const base = AD_EMBED_BASE_URL.trim().replace(/\/$/, '')
  if (!base) return null
  return `${base}/${SURFACE_HTML[surface]}`
}

export function surfaceAdsEnabled(
  surface: AdSurface,
  baseUrl: string,
  enabled: readonly AdSurface[]
): boolean {
  if (!baseUrl.trim()) return false
  return enabled.includes(surface)
}

export function adsEnabled(surface: AdSurface): boolean {
  return surfaceAdsEnabled(surface, AD_EMBED_BASE_URL, AD_ENABLED_SURFACES)
}
