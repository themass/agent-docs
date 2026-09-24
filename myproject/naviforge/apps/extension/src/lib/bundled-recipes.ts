import type { SiteRecipe } from '@naviforge/runtime'

/** Shipped examples — learned/user recipes override by host+intent. */
export const BUNDLED_RECIPES: SiteRecipe[] = [
  {
    id: 'media-extract-default',
    title: '媒体提取：SIGNALS → 点播放 → 等 m3u8',
    hosts: ['*'],
    intent: 'media_extract',
    version: 1,
    source: 'bundled',
    steps: [
      { use: 'page_signals_playback', optional: true },
      { use: 'dom_click', textIncludes: '播放', optional: true },
      { use: 'network_wait', urlIncludes: '.m3u8', timeout_ms: 20_000 },
    ],
  },
]

/** Host-specific media extract recipe (overrides bundled wildcard when saved). */
export function buildMediaExtractRecipe(host: string): SiteRecipe {
  return {
    id: `media-${host.replace(/\./g, '-')}`,
    title: `${host} 媒体提取`,
    hosts: [host],
    intent: 'media_extract',
    version: 1,
    source: 'user',
    steps: [
      { use: 'page_signals_playback', optional: true },
      { use: 'dom_click', textIncludes: '播放', optional: true },
      { use: 'network_wait', urlIncludes: '.m3u8', timeout_ms: 20_000 },
    ],
    createdAt: Date.now(),
  }
}

/** Host-specific document download recipe template (save via site-recipe-store). */
export function buildDocumentDownloadRecipe(host: string): SiteRecipe {
  return {
    id: `download-${host.replace(/\./g, '-')}`,
    title: `${host} 文档下载`,
    hosts: [host],
    intent: 'page_download',
    version: 1,
    source: 'user',
    steps: [
      { use: 'dom_snapshot', mode: 'compact' },
      { use: 'dom_click', textIncludes: '单篇下载', optional: true },
      { use: 'dom_click', textIncludes: '下载', optional: true },
      { use: 'dom_wait', kind: 'download', timeout_ms: 60_000 },
    ],
    createdAt: Date.now(),
  }
}
