/** Shared task-text signals — single source for deliverable + intent classifiers. */

export const MEDIA_TASK =
  /播放|视频|m3u8|mp4|stream|playback|media url|播放地址|流地址|源地址|hls|webm/i

export const SCRIPT_TASK =
  /(?:生成|写|输出|给我).{0,16}(python|py|脚本|scraper|爬虫)|(?:python|py|脚本).{0,24}(抓取|爬取|crawl|scrape|采集)|(?:抓取|爬取).{0,16}(python|脚本)/i

export const EXTRACT_WEAK = /提取|抓取|列出|top\s*\d+|前\s*\d+/

export const DENIED_TASK =
  /破解|绕过.{0,8}加密|破解.{0,8}付费|crack|bypass.{0,12}(drm|paywall|encryption)/i

export const DOWNLOAD_TASK = /下载|download|保存.{0,6}文件|save.{0,8}file/i

export function looksLikeMediaTask(task: string): boolean {
  return MEDIA_TASK.test(task.trim())
}

export function looksLikeScriptTask(task: string): boolean {
  return SCRIPT_TASK.test(task.trim())
}

export function looksLikeWeakExtract(task: string): boolean {
  return EXTRACT_WEAK.test(task.trim())
}

export function looksLikeDeniedTask(task: string): boolean {
  return DENIED_TASK.test(task.trim())
}

export function looksLikeDownloadTask(task: string): boolean {
  return DOWNLOAD_TASK.test(task.trim())
}
