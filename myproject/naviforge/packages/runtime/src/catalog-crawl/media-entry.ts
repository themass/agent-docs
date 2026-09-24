import { classifyMediaUrl } from '@naviforge/media-plane'

/** Playback evidence format for catalog / spawn output schema. */
export type MediaPlaybackFormat = 'hls' | 'dash' | 'mp4' | 'webm' | 'embed' | 'unknown'

export function mapHintKindToFormat(kind: ReturnType<typeof classifyMediaUrl>): MediaPlaybackFormat {
  if (kind === 'hls') return 'hls'
  if (kind === 'dash') return 'dash'
  if (kind === 'mp4') return 'mp4'
  if (kind === 'segment') return 'hls'
  return 'unknown'
}

export function classifyPlaybackUrl(url: string): MediaPlaybackFormat {
  const kind = classifyMediaUrl(url)
  if (kind === 'mp4' && /\.webm/i.test(url)) return 'webm'
  return mapHintKindToFormat(kind)
}

export function entryHasPlayableEvidence(entry: {
  mediaUrl?: string
  playPageUrl?: string
}): boolean {
  return Boolean(entry.mediaUrl?.trim() || entry.playPageUrl?.trim())
}

export function isLikelyPlayPageUrl(url: string): boolean {
  try {
    const path = new URL(url).pathname.toLowerCase()
    return /\/(play|video|watch|stream|player|vodplay|embed)\//.test(path)
  } catch {
    return false
  }
}

/** Pinned in KERNEL/GUIDANCE — agent + spawn children use this shape. */
export const MEDIA_ENTRY_OUTPUT_SCHEMA = `每条媒体条目输出 schema（父/子任务 system_done 均遵守）：
{
  "title": string,
  "listUrl"?: string,        // 列表/详情链接
  "mediaUrl"?: string,       // 直链：m3u8/mpd/mp4/webm/…
  "playPageUrl"?: string,    // 无直链时的播放/embed/内嵌页
  "format"?: "hls"|"dash"|"mp4"|"webm"|"embed"|"unknown",
  "confidence"?: number,     // 0–1
  "shortfall"?: string       // 为何无直链、需点击播放、blob/DRM 等
}
规则：有直链写 mediaUrl+format；仅 iframe/内嵌播放器写 playPageUrl+shortfall；多个候选由模型结合 PAGE SIGNALS 选主播放流。`

export const MEDIA_AGENT_JUDGMENT_GUIDANCE = [
  'GUIDANCE: 视频源不限 m3u8 — mp4/webm/dash(mpd)/hls 均可；无直链可输出 playPageUrl（内嵌播放页）。',
  'GUIDANCE: 列表页通常无直链 — spawn 打开详情/播放页，读 PAGE SIGNALS；需点播放时用 dom_click + network_read。',
  'GUIDANCE: blob:/MediaSource/DRM — 禁止逆向；shortfall 说明 + 给 playPageUrl 或 listUrl。',
  'GUIDANCE: preflight 预算外条目（>24）— system_spawn_readonly_tasks 每批≤3，子 prompt 要求返回 MEDIA_ENTRY schema。',
] as const
