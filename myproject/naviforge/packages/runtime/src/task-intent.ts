import {
  isCatalogCrawlTask,
  isPageReadTask,
  isResearchTask,
  isSiteCatalogSopTask,
  resolveTaskMode,
  shouldHintListThenDetail,
} from './task-classifier.js'

export type TaskIntent =
  | 'page_read'
  | 'page_download'
  | 'media_extract'
  | 'list_extract'
  | 'multi_hop_crawl'
  | 'research'
  | 'general'
  | 'list_detail'
  | 'denied'

const DENIED = /破解|绕过.{0,8}加密|破解.{0,8}付费|crack|bypass.{0,12}(drm|paywall|encryption)/i

const MEDIA_TASK =
  /播放|视频|m3u8|mp4|stream|playback|media url|播放地址|流地址|源地址|hls|webm/i

export function isMediaTask(task: string): boolean {
  return MEDIA_TASK.test(task)
}

export function resolveTaskIntent(task: string): TaskIntent {
  const t = task.trim()
  if (DENIED.test(t)) return 'denied'
  if (isMediaTask(t)) return 'media_extract'
  if (/下载|download|保存.{0,6}文件|save.{0,8}file/i.test(t)) return 'page_download'
  if (isSiteCatalogSopTask(t) || isCatalogCrawlTask(t)) return 'multi_hop_crawl'
  if (shouldHintListThenDetail(t)) return 'list_detail'
  if (isResearchTask(t)) return 'research'
  if (isPageReadTask(t)) return 'page_read'
  if (/提取|抓取|列出|top\s*\d+|前\s*\d+/.test(t) && !isPageReadTask(t)) return 'list_extract'
  if (resolveTaskMode(t) === 'general') return 'general'
  return 'page_read'
}

export function intentPreflightSkill(intent: TaskIntent): string | undefined {
  switch (intent) {
    case 'page_download':
      return 'document-download'
    case 'media_extract':
      return 'media-extract'
    case 'list_detail':
      return 'page-friction'
    case 'multi_hop_crawl':
      return 'catalog-crawl-sop'
    case 'research':
      return 'research-compare'
    case 'page_read':
      return 'page-read'
    default:
      return undefined
  }
}

export function intentGuidanceNotes(intent: TaskIntent): string[] {
  switch (intent) {
    case 'denied':
      return [
        'CONSTRAINT: 拒绝破解加密/DRM/付费绕过。system_done 说明合法替代（登录、官方下载、page_to_pdf 可见部分）。',
      ]
    case 'page_download':
      return [
        'GUIDANCE: intent=download — skill document-download：snapshot 找下载按钮 → dom_click → dom_wait kind=download → system_done 含文件名；勿 dom_read 循环；登录/VIP 用 system_ask_user；兜底 page_to_pdf。',
        'CONSTRAINT: 禁止 web_search / tabs_open 无关 URL。',
      ]
    case 'media_extract':
      return [
        'GUIDANCE: intent=media — PAGE SIGNALS 优先；无直链则 dom_click 播放 → network_read/media；输出 mediaUrl+format；列表页用 catalog-crawl spawn；禁止 DRM 逆向。',
        'CONSTRAINT: 「下载视频文件」= 先 mediaUrl，再 script_save/ffmpeg（Host）；浏览器不拉 HLS 分片。',
      ]
    case 'multi_hop_crawl':
      return [
        'GUIDANCE: intent=crawl — catalog-crawl-sop Phase 0–5；列表 extract → spawn≤3 读详情；禁止父 tab 串行点开列表项。',
      ]
    case 'list_extract':
      return [
        'GUIDANCE: intent=extract — dom_read list 或 system_extract_page 一次；够则 system_done；勿反复 snapshot。',
      ]
    case 'list_detail':
      return [
        'GUIDANCE: intent=list_detail — skill list-then-detail：list → 打开第 k 条 → 读详情 → system_done。',
      ]
    case 'research':
      return [
        'GUIDANCE: intent=research — web_search → tabs_open 2–3 源 → dom_read body → 对比 system_done。',
      ]
    case 'general':
      return [
        'GUIDANCE: intent=general — THREAD/CONTEXT 优先；壳页勿 dom_snapshot 空转。',
      ]
    case 'page_read':
      return [
        'GUIDANCE: intent=read — dom_read body 一次 → system_done；禁止 scroll-hunt。',
      ]
  }
}
