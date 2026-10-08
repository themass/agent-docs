import {
  isCatalogCrawlTask,
  isPageReadTask,
  isResearchTask,
  isSiteCatalogSopTask,
  resolveTaskMode,
  shouldHintListThenDetail,
} from './task-classifier.js'
import { isScriptDeliverableTask, resolveDeliverable } from './deliverable.js'

export type TaskIntent =
  | 'page_read'
  | 'page_download'
  | 'media_extract'
  | 'script_authoring'
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
  if (isScriptDeliverableTask(t) || resolveDeliverable(t) === 'script') return 'script_authoring'
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
      return 'persist'
    case 'media_extract':
      return 'harvest'
    case 'script_authoring':
      return 'persist'
    case 'list_detail':
      return 'traverse'
    case 'multi_hop_crawl':
      return 'traverse'
    case 'research':
      return 'research'
    case 'page_read':
      return 'observe'
    default:
      return undefined
  }
}

export function intentGuidanceNotes(intent: TaskIntent): string[] {
  switch (intent) {
    case 'denied':
      return [
        'CONSTRAINT: 拒绝破解加密/DRM/付费绕过。system_done 说明合法替代（登录、官方下载、pdf 可见部分）。',
      ]
    case 'page_download':
      return [
        'GUIDANCE: intent=download — persist：找下载按钮 → click → wait download → system_done 含文件名；登录/VIP 用 system_ask_user；兜底 pdf。',
        'CONSTRAINT: 禁止 web_search / 无关 URL。',
      ]
    case 'media_extract':
      return [
        'GUIDANCE: intent=media — PAGE SIGNALS 优先；无直链则 click 播放 → network media/hls；输出 mediaUrl+format；列表页 spawn；禁止 DRM 逆向。',
        'CONSTRAINT: 「下载视频文件」= 先 mediaUrl，再 script_save/ffmpeg（Host）；浏览器不拉 HLS 分片。',
        'GUIDANCE: navigation:forbidden 时父 tab 勿 browser_nav；用 spawn 打开详情/播放页（mode:tab）+ network。',
      ]
    case 'script_authoring':
      return [
        'GUIDANCE: intent=script — 读 PAGE STATE；采样分类/分页 URL；workspace script_save Python（pages 默认 1）；system_done 附 path。',
        'CONSTRAINT: 禁止 media_extract recipe、MEDIA_ENTRY、full-catalog crawl、spawn 媒体子任务。',
      ]
    case 'multi_hop_crawl':
      return [
        'GUIDANCE: intent=crawl — traverse：列表 extract → spawn≤3 读详情；禁止父 tab 串行点开列表项。',
      ]
    case 'list_extract':
      return [
        'GUIDANCE: intent=extract — browser_observe read list 或 extract 一次；够则 system_done；勿反复 snapshot。',
      ]
    case 'list_detail':
      return [
        'GUIDANCE: intent=list_detail — traverse：list → 打开第 k 条 → 读详情 → system_done。',
      ]
    case 'research':
      return [
        'GUIDANCE: intent=research — web_search → tabs open 2–3 源 → observe read → 对比 system_done。',
      ]
    case 'general':
      return [
        'GUIDANCE: intent=general — THREAD/CONTEXT 优先；壳页勿 dom_snapshot 空转。',
      ]
    case 'page_read':
      return [
        'GUIDANCE: intent=read — browser_observe read body 一次 → system_done；禁止 scroll-hunt。',
      ]
  }
}
