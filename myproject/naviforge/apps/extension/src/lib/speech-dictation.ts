/** Chrome Web Speech. Empty string = ignore (silence / abort). */

import type { LocalePreference } from '../i18n/locales'
import { browserLanguages } from '../i18n/locales'
import {
  DEFAULT_SPEECH_TARGETS,
  getCachedLastSpeechLang,
  isSpeechRecognitionLang,
  persistLastSpeechLang,
  type SpeechLangConfig,
  type SpeechRecognitionLang,
} from './speech-lang'

export { getCachedLastSpeechLang, persistLastSpeechLang } from './speech-lang'
export type { SpeechLangConfig, SpeechRecognitionLang } from './speech-lang'

export function speechErrorMessage(code: string): string {
  if (code === 'no-speech' || code === 'aborted') return ''
  if (code === 'not-allowed' || code === 'service-not-allowed') {
    return '没有麦克风权限。请在 Chrome 站点设置里允许 NaviForge 使用麦克风。'
  }
  if (code === 'audio-capture') return '没有找到麦克风'
  if (code === 'network') return '语音识别需要网络（Chrome 会把声音发到 Google 识别服务）'
  return `语音识别失败（${code}）`
}

/** i18n key under `chat.speech.*`; null = no user-visible error. */
export function speechErrorI18nKey(code: string): string | null {
  if (code === 'no-speech' || code === 'aborted') return null
  if (code === 'not-allowed' || code === 'service-not-allowed') return 'chat.speech.notAllowed'
  if (code === 'audio-capture') return 'chat.speech.missing'
  if (code === 'network') return 'chat.speech.network'
  return 'chat.speech.failed'
}

/** Only `no-speech` should keep the session alive; other errors restart into a loop. */
export function dictationShouldKeepListening(code: string): boolean {
  return code === 'no-speech'
}

export function appendDictation(existing: string, chunk: string): string {
  const add = chunk.trim()
  if (!add) return existing
  const base = existing.trimEnd()
  if (!base) return add
  if (/[\u4e00-\u9fff]$/.test(base) || /^[\u4e00-\u9fff]/.test(add)) return `${base}${add}`
  return `${base} ${add}`
}

export function extensionSiteSettingsUrl(): string {
  const id = globalThis.chrome?.runtime?.id
  if (!id) return 'chrome://settings/content/microphone'
  return `chrome://settings/content/siteDetails?site=${encodeURIComponent(`chrome-extension://${id}`)}`
}

export async function openExtensionSiteSettings(): Promise<void> {
  const url = extensionSiteSettingsUrl()
  if (typeof chrome !== 'undefined' && chrome.tabs) {
    await chrome.tabs.create({ url })
    return
  }
  window.open(url, '_blank')
}

/** Trigger the browser permission prompt before Web Speech (extension origin). */
export async function ensureMicrophoneAccess(): Promise<
  { ok: true } | { ok: false; reason: 'unsupported' | 'denied' | 'missing' }
> {
  if (!navigator.mediaDevices?.getUserMedia) return { ok: false, reason: 'unsupported' }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    stream.getTracks().forEach((track) => track.stop())
    return { ok: true }
  } catch (error) {
    const name =
      error && typeof error === 'object' && 'name' in error ? String((error as { name: string }).name) : ''
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') return { ok: false, reason: 'missing' }
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') return { ok: false, reason: 'denied' }
    return { ok: false, reason: 'denied' }
  }
}

type SpeechRec = {
  lang: string
  continuous: boolean
  interimResults: boolean
  start: () => void
  stop: () => void
  abort: () => void
  onresult: ((event: SpeechRecEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}

type SpeechRecEvent = {
  resultIndex: number
  results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }>
}

export function getSpeechRecognitionCtor(): (new () => SpeechRec) | null {
  const rec = globalThis as typeof globalThis & {
    SpeechRecognition?: new () => SpeechRec
    webkitSpeechRecognition?: new () => SpeechRec
  }
  return rec.SpeechRecognition ?? rec.webkitSpeechRecognition ?? null
}

/** Map shipped UI locale to a Web Speech BCP-47 tag. */
export function localeToSpeechLang(locale: string): SpeechRecognitionLang {
  if (locale === 'zh-CN') return 'zh-CN'
  if (locale === 'es') return 'es-ES'
  return 'en-US'
}

function pickInTargets(
  lang: string | null | undefined,
  targets: readonly string[]
): SpeechRecognitionLang | null {
  if (!lang) return null
  if (targets.includes(lang) && isSpeechRecognitionLang(lang)) return lang
  const base = lang.split('-')[0]!
  for (const target of targets) {
    if (target.startsWith(base) && isSpeechRecognitionLang(target)) return target
  }
  return null
}

/** Map browser language tags to Web Speech tags Chrome commonly accepts. */
export function browserTagToSpeechLang(tag: string): string | null {
  const normalized = tag.trim().toLowerCase().replace(/_/g, '-')
  if (!normalized) return null
  if (normalized === 'zh' || normalized.startsWith('zh-')) {
    return normalized.includes('tw') || normalized.includes('hk') ? 'zh-TW' : 'zh-CN'
  }
  if (normalized === 'es' || normalized.startsWith('es-')) return 'es-ES'
  if (normalized === 'en' || normalized.startsWith('en-')) return 'en-US'
  if (normalized === 'ja' || normalized.startsWith('ja-')) return 'ja-JP'
  if (normalized === 'ko' || normalized.startsWith('ko-')) return 'ko-KR'
  if (normalized === 'fr' || normalized.startsWith('fr-')) return 'fr-FR'
  if (normalized === 'de' || normalized.startsWith('de-')) return 'de-DE'
  return null
}

/** Guess speech lang from visible script in composer text (short hints ignored). */
export function detectSpeechLangFromText(text: string): string | null {
  const sample = text.trim()
  if (sample.length < 2) return null
  let cjk = 0
  let kana = 0
  let hangul = 0
  let latin = 0
  for (const ch of sample) {
    const code = ch.codePointAt(0)!
    if (code >= 0x4e00 && code <= 0x9fff) cjk += 1
    else if ((code >= 0x3040 && code <= 0x30ff) || (code >= 0x31f0 && code <= 0x31ff)) kana += 1
    else if (code >= 0xac00 && code <= 0xd7af) hangul += 1
    else if (/[a-z]/i.test(ch)) latin += 1
  }
  if (cjk > 0 && kana === 0 && hangul === 0 && latin === 0) return 'zh-CN'
  if (kana > 0 && kana >= cjk) return 'ja-JP'
  if (hangul > 0 && hangul >= cjk) return 'ko-KR'
  const total = cjk + kana + hangul + latin
  if (total < 4) return null
  if (kana / total >= 0.12) return 'ja-JP'
  if (hangul / total >= 0.12) return 'ko-KR'
  if (cjk / total >= 0.2) return 'zh-CN'
  if (latin / total >= 0.6 && cjk === 0 && kana === 0 && hangul === 0) return 'en-US'
  return null
}

/**
 * Pick Web Speech `lang` within configured targets.
 * Fixed mode uses one language; auto mode detects among targets (one at a time per Chrome).
 */
export function resolveSpeechRecognitionLang(opts?: {
  config?: Pick<SpeechLangConfig, 'mode' | 'targets' | 'fixed'>
  hintText?: string
  languages?: readonly string[]
  lastSpeechLang?: string | null
}): SpeechRecognitionLang {
  const config = opts?.config
  const targets =
    config?.mode === 'fixed'
      ? [config.fixed]
      : normalizeTargets(config?.targets ?? DEFAULT_SPEECH_TARGETS)

  if (config?.mode === 'fixed') return config.fixed

  const fromText = pickInTargets(detectSpeechLangFromText(opts?.hintText ?? ''), targets)
  if (fromText) return fromText

  // Auto with multiple targets: honor list order over stale last-lang cache (English Chrome
  // otherwise keeps en-US and Chinese speech becomes "no no" gibberish).
  if (config?.mode === 'auto' && targets.length > 1) {
    return targets[0]!
  }

  const last = pickInTargets(opts?.lastSpeechLang ?? getCachedLastSpeechLang(), targets)
  if (last) return last

  for (const raw of opts?.languages ?? browserLanguages()) {
    const mapped = pickInTargets(browserTagToSpeechLang(raw), targets)
    if (mapped) return mapped
  }

  return (targets[0] ?? 'en-US') as SpeechRecognitionLang
}

function normalizeTargets(targets: readonly string[]): SpeechRecognitionLang[] {
  const out: SpeechRecognitionLang[] = []
  for (const item of targets) {
    if (isSpeechRecognitionLang(item) && !out.includes(item)) out.push(item)
  }
  return out.length ? out : [...DEFAULT_SPEECH_TARGETS]
}

/** Drop leading English noise Chrome emits before CJK when lang was wrong. */
export function stripLeadingLatinBeforeCjk(text: string): string {
  const idx = text.search(/[\u4e00-\u9fff]/)
  if (idx <= 0) return text
  const prefix = text.slice(0, idx).trim()
  if (!prefix || !/^[a-z0-9\s.,!?'-]+$/i.test(prefix)) return text
  return text.slice(idx).trimStart()
}

function shouldSwitchSpeechLang(
  current: string,
  detected: string,
  text: string,
  targets: readonly string[]
): boolean {
  if (current === detected || !targets.includes(detected)) return false
  const cjk = /[\u4e00-\u9fff]/.test(text)
  const kana = /[\u3040-\u30ff]/.test(text)
  const hangul = /[\uac00-\ud7af]/.test(text)
  const latin = /[a-z]/i.test(text)
  if (detected === 'zh-CN' && targets.includes('zh-CN')) {
    if (cjk || (current.startsWith('en') && looksLikeMisrecognizedEnglish(text))) return true
  }
  if (detected === 'ja-JP' && kana) return true
  if (detected === 'ko-KR' && hangul) return true
  if (detected === 'en-US' && latin && !cjk && !kana && !hangul) return true
  if (detected === 'es-ES' && latin && !cjk) return true
  return false
}

function looksLikeMisrecognizedEnglish(text: string): boolean {
  const sample = text.trim()
  if (sample.length < 6 || /[\u4e00-\u9fff]/.test(sample)) return false
  if (!/^[a-z0-9\s.,!?'-]+$/i.test(sample)) return false
  const words = sample.split(/\s+/).filter(Boolean)
  if (words.length < 3) return false
  const short = words.filter((word) => word.length <= 2).length
  return short / words.length >= 0.45
}

export function createDictation(opts: {
  getLang?: () => string
  getTargetLangs?: () => readonly string[]
  onFinal: (chunk: string) => void
  onInterim: (text: string) => void
  onError: (code: string) => void
  onEnd: () => void
}): { start: () => boolean; stop: () => void; refreshLang: () => void } | null {
  const maybeCtor = getSpeechRecognitionCtor()
  if (!maybeCtor) return null
  const Recognition: new () => SpeechRec = maybeCtor
  let want = false
  let rec: SpeechRec | null = null
  let switchedLang = false

  function targetLangs(): readonly string[] {
    const custom = opts.getTargetLangs?.()
    return custom?.length ? custom : DEFAULT_SPEECH_TARGETS
  }

  function resolveLang(): string {
    return opts.getLang?.() ?? resolveSpeechRecognitionLang({ languages: browserLanguages() })
  }

  function cleanTranscript(text: string): string {
    const sample = text.trim()
    if (!sample) return sample
    const lang = rec?.lang ?? resolveLang()
    if (lang.startsWith('zh') || targetLangs().includes('zh-CN')) {
      return stripLeadingLatinBeforeCjk(sample)
    }
    return sample
  }

  function maybeSwitchLang(text: string): void {
    const sample = text.trim()
    if (!sample || !rec || !want) return
    const targets = targetLangs()
    let detected = detectSpeechLangFromText(sample)
    if (
      !detected &&
      rec.lang.startsWith('en') &&
      targets.includes('zh-CN') &&
      /[\u4e00-\u9fff]/.test(sample)
    ) {
      detected = 'zh-CN'
    }
    if (
      !detected &&
      rec.lang.startsWith('en') &&
      targets.includes('zh-CN') &&
      looksLikeMisrecognizedEnglish(sample)
    ) {
      detected = 'zh-CN'
    }
    if (!detected || !shouldSwitchSpeechLang(rec.lang, detected, sample, targets)) return
    switchedLang = true
    persistLastSpeechLang(detected)
    rec.lang = detected
    try {
      rec.stop()
    } catch {
      /* onend restarts */
    }
  }

  function start(): boolean {
    if (want) return true
    want = true
    switchedLang = false
    rec = new Recognition()
    rec.lang = resolveLang()
    rec.continuous = true
    rec.interimResults = true
    rec.onresult = (event) => {
      let finalChunk = ''
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const piece = event.results[i]
        if (!piece) continue
        if (piece.isFinal) finalChunk += piece[0].transcript
        else interim += piece[0].transcript
      }
      if (finalChunk) {
        const cleaned = cleanTranscript(finalChunk)
        const detected = detectSpeechLangFromText(cleaned)
        if (detected) persistLastSpeechLang(detected)
        opts.onFinal(cleaned)
        maybeSwitchLang(cleaned)
      }
      if (interim.trim()) {
        const cleaned = cleanTranscript(interim)
        maybeSwitchLang(cleaned)
        opts.onInterim(cleaned)
      } else {
        opts.onInterim('')
      }
    }
    rec.onerror = (event) => {
      if (!dictationShouldKeepListening(event.error)) want = false
      opts.onError(event.error)
    }
    rec.onend = () => {
      // ponytail: Chrome stops after a pause; restart while the user still wants to talk.
      if (want && rec) {
        try {
          rec.lang = resolveLang()
          rec.start()
          return
        } catch {
          want = false
        }
      }
      rec = null
      opts.onInterim('')
      opts.onEnd()
    }
    try {
      rec.start()
      return true
    } catch (error) {
      want = false
      rec = null
      opts.onError(error instanceof Error ? error.message : 'start-failed')
      return false
    }
  }

  function stop(): void {
    want = false
    rec?.stop()
  }

  function refreshLang(): void {
    if (!rec || !want) return
    const next = resolveLang()
    if (rec.lang === next) return
    rec.lang = next
    try {
      rec.stop()
    } catch {
      /* onend restarts */
    }
  }

  return { start, stop, refreshLang }
}
