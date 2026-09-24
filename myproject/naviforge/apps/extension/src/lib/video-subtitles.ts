import { translateTextsGtx } from './page-translate'

export type CaptionTrack = {
  lang: string
  label: string
  url?: string
  kind?: string
}

export type Cue = { start: number; end: number; text: string }
export type OverlayCue = Cue & { translated: string }

export type CaptionSource = {
  site: 'youtube' | 'bilibili' | 'html5' | 'unknown'
  videoPresent: boolean
  tracks: CaptionTrack[]
}

export function isZhLang(lang: string): boolean {
  return /^(zh|chi|yue|cmn|ai-zh)/i.test(lang.trim())
}

export function parseVttTime(raw: string): number {
  const clean = raw.trim().split(/\s+/)[0]?.replace(',', '.') ?? '0'
  const parts = clean.split(':').map(Number)
  if (parts.some((n) => Number.isNaN(n))) return 0
  if (parts.length === 3) return parts[0]! * 3600 + parts[1]! * 60 + parts[2]!
  if (parts.length === 2) return parts[0]! * 60 + parts[1]!
  return parts[0] ?? 0
}

export function parseWebVtt(raw: string): Cue[] {
  const cues: Cue[] = []
  const blocks = raw.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').split(/\n\n+/)
  for (const block of blocks) {
    const lines = block.trim().split('\n')
    const timeLine = lines.find((line) => line.includes('-->'))
    if (!timeLine) continue
    const [startRaw, endRaw] = timeLine.split('-->')
    if (!startRaw || !endRaw) continue
    const text = lines
      .slice(lines.indexOf(timeLine) + 1)
      .join(' ')
      .replace(/<[^>]+>/g, '')
      .trim()
    if (!text) continue
    cues.push({ start: parseVttTime(startRaw), end: parseVttTime(endRaw), text })
  }
  return cues
}

export function parseYoutubeJson3(data: unknown): Cue[] {
  if (!data || typeof data !== 'object' || !('events' in data)) return []
  const events = (data as { events?: unknown }).events
  if (!Array.isArray(events)) return []
  const cues: Cue[] = []
  for (const event of events) {
    if (!event || typeof event !== 'object') continue
    const row = event as {
      tStartMs?: number
      dDurationMs?: number
      segs?: Array<{ utf8?: string }>
    }
    if (row.tStartMs == null || !row.segs?.length) continue
    const text = row.segs
      .map((seg) => seg.utf8 ?? '')
      .join('')
      .replace(/\n/g, ' ')
      .trim()
    if (!text) continue
    const start = row.tStartMs / 1000
    cues.push({ start, end: start + (row.dDurationMs ?? 2000) / 1000, text })
  }
  return cues
}

export function parseBilibiliJson(raw: string): Cue[] {
  let data: unknown
  try {
    data = JSON.parse(raw) as unknown
  } catch {
    return []
  }
  const body =
    data && typeof data === 'object' && 'body' in data
      ? (data as { body?: unknown }).body
      : undefined
  if (!Array.isArray(body)) return []
  const cues: Cue[] = []
  for (const row of body) {
    if (!row || typeof row !== 'object') continue
    const item = row as { from?: number; to?: number; content?: string }
    const text = String(item.content ?? '').trim()
    if (!text || item.from == null || item.to == null) continue
    cues.push({ start: item.from, end: item.to, text })
  }
  return cues
}

export function pickCaptionTrack(tracks: CaptionTrack[]): CaptionTrack | null {
  if (!tracks.length) return null
  const withUrl = tracks.filter((track) => track.url)
  const pool = withUrl.length ? withUrl : tracks
  const scored = pool.map((track) => {
    const auto = /auto|asr|自动/i.test(`${track.label} ${track.kind ?? ''}`)
    const en = /^en\b/i.test(track.lang)
    const zh = isZhLang(track.lang)
    let score = 0
    if (en && !auto) score = 4
    else if (en) score = 3
    else if (!zh && !auto) score = 2
    else if (!zh) score = 1
    else score = 0
    return { track, score }
  })
  scored.sort((a, b) => b.score - a.score)
  return scored[0]?.track ?? null
}

export function cueAt(cues: OverlayCue[], time: number): OverlayCue | null {
  let lo = 0
  let hi = cues.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (cues[mid]!.start <= time) {
      found = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  if (found < 0) return null
  const cue = cues[found]!
  return time < cue.end ? cue : null
}

/** Injectable: MAIN world. Reads YouTube / Bilibili player globals. */
export function scrapeCaptionSource(): CaptionSource {
  const video = document.querySelector('video')
  const html5: CaptionTrack[] = []
  if (video) {
    const tracks = video.textTracks
    for (let i = 0; i < tracks.length; i += 1) {
      const track = tracks[i]
      if (!track) continue
      if (track.kind !== 'subtitles' && track.kind !== 'captions') continue
      html5.push({ lang: track.language || 'und', label: track.label || track.language })
    }
  }

  const win = window as Window & {
    ytInitialPlayerResponse?: {
      captions?: {
        playerCaptionsTracklistRenderer?: {
          captionTracks?: Array<{
            baseUrl?: string
            languageCode?: string
            kind?: string
            name?: { simpleText?: string }
          }>
        }
      }
    }
    __playinfo__?: {
      data?: {
        subtitle?: { subtitles?: Array<{ lan?: string; lan_doc?: string; subtitle_url?: string }> }
      }
    }
    __INITIAL_STATE__?: {
      subtitle?: { subtitles?: Array<{ lan?: string; lan_doc?: string; subtitle_url?: string }> }
    }
  }

  const player = document.getElementById('movie_player') as {
    getPlayerResponse?: () => unknown
  } | null
  let yt = win.ytInitialPlayerResponse
  if (!yt && player?.getPlayerResponse) {
    try {
      yt = player.getPlayerResponse() as typeof yt
    } catch {
      yt = undefined
    }
  }
  const ytTracks = (yt?.captions?.playerCaptionsTracklistRenderer?.captionTracks ?? []).flatMap(
    (track) =>
      track.baseUrl
        ? [
            {
              lang: track.languageCode ?? 'und',
              label: track.name?.simpleText ?? track.languageCode ?? '',
              url: track.baseUrl,
              kind: track.kind,
            },
          ]
        : []
  )
  if (ytTracks.length) {
    return { site: 'youtube', videoPresent: Boolean(video), tracks: ytTracks }
  }

  const biliList =
    win.__playinfo__?.data?.subtitle?.subtitles ?? win.__INITIAL_STATE__?.subtitle?.subtitles ?? []
  const biliTracks = biliList.flatMap((item) => {
    const raw = item.subtitle_url
    if (!raw) return []
    const url = raw.startsWith('//') ? `https:${raw}` : raw
    return [{ lang: item.lan ?? 'und', label: item.lan_doc ?? item.lan ?? '', url }]
  })
  if (biliTracks.length) {
    return { site: 'bilibili', videoPresent: Boolean(video), tracks: biliTracks }
  }

  return {
    site: html5.length ? 'html5' : 'unknown',
    videoPresent: Boolean(video),
    tracks: html5,
  }
}

export function readHtml5Cues(): Cue[] {
  const video = document.querySelector('video')
  if (!video) return []
  const out: Cue[] = []
  const tracks = video.textTracks
  for (let i = 0; i < tracks.length; i += 1) {
    const track = tracks[i]
    if (!track) continue
    if (track.kind !== 'subtitles' && track.kind !== 'captions') continue
    const prev = track.mode
    track.mode = 'hidden'
    const cues = track.cues
    if (!cues?.length) {
      track.mode = prev
      continue
    }
    for (let j = 0; j < cues.length; j += 1) {
      const cue = cues[j] as TextTrackCue & { text?: string }
      const text = String(cue.text ?? '')
        .replace(/<[^>]+>/g, '')
        .trim()
      if (!text) continue
      out.push({ start: cue.startTime, end: cue.endTime, text })
    }
    track.mode = prev
    if (out.length) break
  }
  return out
}

export async function translateCues(cues: Cue[], sourceLang: string): Promise<OverlayCue[]> {
  if (!cues.length) return []
  if (isZhLang(sourceLang)) return cues.map((cue) => ({ ...cue, translated: cue.text }))
  const unique: string[] = []
  const at = new Map<string, number>()
  for (const cue of cues) {
    if (!at.has(cue.text)) {
      at.set(cue.text, unique.length)
      unique.push(cue.text)
    }
  }
  // ponytail: unique-line cap; a feature film can exceed 2k cues. Raise if movies truncate.
  const slice = unique.slice(0, 800)
  const translated = await translateTextsGtx(slice, 'zh-CN')
  return cues.map((cue) => {
    const index = at.get(cue.text) ?? 0
    return { ...cue, translated: translated[index] ?? cue.text }
  })
}

async function fetchCaptionText(url: string, tabId: number): Promise<string> {
  try {
    const response = await fetch(url)
    if (response.ok) return await response.text()
  } catch {
    // fall through to the page origin, which has cookies
  }
  const [injected] = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN',
    func: async (href: string) => {
      const response = await fetch(href)
      if (!response.ok) throw new Error(`caption HTTP ${response.status}`)
      return response.text()
    },
    args: [url],
  })
  if (typeof injected?.result !== 'string') throw new Error('无法下载字幕轨')
  return injected.result
}

export async function cuesFromTrack(
  track: CaptionTrack,
  site: CaptionSource['site'],
  tabId: number
): Promise<Cue[]> {
  if (!track.url) {
    const [injected] = await chrome.scripting.executeScript({
      target: { tabId },
      func: readHtml5Cues,
    })
    return Array.isArray(injected?.result) ? (injected.result as Cue[]) : []
  }
  let href = track.url
  if (site === 'youtube') {
    const parsed = new URL(track.url, 'https://www.youtube.com')
    parsed.searchParams.set('fmt', 'json3')
    href = parsed.toString()
  }
  const raw = await fetchCaptionText(href, tabId)
  if (site === 'bilibili') return parseBilibiliJson(raw)
  const trimmed = raw.trimStart()
  if (trimmed.startsWith('{')) {
    try {
      const parsed = parseYoutubeJson3(JSON.parse(raw) as unknown)
      if (parsed.length) return parsed
    } catch {
      // try vtt below
    }
  }
  if (raw.includes('-->')) return parseWebVtt(raw)
  return []
}

type SubtitleControlResponse = {
  success?: boolean
  active?: boolean
  error?: string
}

async function sendSubtitleControl(
  tabId: number,
  payload: { op: 'start' | 'stop' | 'status'; cues?: OverlayCue[] }
): Promise<SubtitleControlResponse> {
  const message = {
    type: 'PAGE_CONTROL',
    action: 'video_subtitles',
    targetTabId: tabId,
    payload,
  }
  try {
    return (await chrome.tabs.sendMessage(tabId, message)) as SubtitleControlResponse
  } catch {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content-scripts/content.js'],
    })
    return (await chrome.tabs.sendMessage(tabId, message)) as SubtitleControlResponse
  }
}

export async function toolkitToggleVideoSubtitles(tab: chrome.tabs.Tab): Promise<{
  ok: boolean
  active?: boolean
  error?: string
  message?: string
}> {
  if (!tab.id || !tab.url) return { ok: false, error: '没有可处理的网页标签' }
  const tabId = tab.id
  const status = await sendSubtitleControl(tabId, { op: 'status' })
  if (status.active) {
    await sendSubtitleControl(tabId, { op: 'stop' })
    return { ok: true, active: false, message: '已关闭视频字幕' }
  }

  const [scraped] = await chrome.scripting.executeScript({
    target: { tabId },
    world: 'MAIN',
    func: scrapeCaptionSource,
  })
  const source = (scraped?.result ?? {
    site: 'unknown',
    videoPresent: false,
    tracks: [],
  }) as CaptionSource
  if (!source.videoPresent) {
    return { ok: false, error: '当前页没有检测到视频' }
  }
  const track = pickCaptionTrack(source.tracks)
  if (!track) {
    return { ok: false, error: '这个播放器没有文字字幕轨（实时听译还没做）' }
  }
  const cues = await cuesFromTrack(track, source.site, tabId)
  if (!cues.length) {
    return { ok: false, error: '字幕轨是空的，换一条语言再试' }
  }
  const overlay = await translateCues(cues, track.lang)
  const started = await sendSubtitleControl(tabId, { op: 'start', cues: overlay })
  if (!started.success) return { ok: false, error: started.error ?? '无法贴上字幕' }
  const message = isZhLang(track.lang)
    ? `已贴上字幕（${track.label || track.lang}，可拖动）`
    : `已翻译字幕（${track.label || track.lang} → 中文，可拖动）`
  return { ok: true, active: true, message }
}
