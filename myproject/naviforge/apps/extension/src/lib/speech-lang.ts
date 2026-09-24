import { useCallback, useEffect, useState } from 'react'

import { STORAGE } from './settings'

/** Web Speech BCP-47 tags NaviForge supports. */
export const SPEECH_RECOGNITION_LANGS = [
  { id: 'zh-CN', labelKey: 'options.speechLangZh' as const },
  { id: 'en-US', labelKey: 'options.speechLangEn' as const },
  { id: 'es-ES', labelKey: 'options.speechLangEs' as const },
  { id: 'ja-JP', labelKey: 'options.speechLangJa' as const },
  { id: 'ko-KR', labelKey: 'options.speechLangKo' as const },
] as const

export type SpeechRecognitionLang = (typeof SPEECH_RECOGNITION_LANGS)[number]['id']

export const DEFAULT_SPEECH_TARGETS: SpeechRecognitionLang[] = [
  'zh-CN',
  'en-US',
  'es-ES',
  'ja-JP',
  'ko-KR',
]

export type SpeechLangMode = 'auto' | 'fixed'

export type SpeechLangConfig = {
  mode: SpeechLangMode
  targets: SpeechRecognitionLang[]
  fixed: SpeechRecognitionLang
}

export const DEFAULT_SPEECH_LANG_CONFIG: SpeechLangConfig = {
  mode: 'fixed',
  targets: ['zh-CN'],
  fixed: 'zh-CN',
}

export function isSpeechRecognitionLang(value: string): value is SpeechRecognitionLang {
  return SPEECH_RECOGNITION_LANGS.some((item) => item.id === value)
}

export function normalizeSpeechTargets(value: unknown): SpeechRecognitionLang[] {
  if (!Array.isArray(value)) return [...DEFAULT_SPEECH_TARGETS]
  const out: SpeechRecognitionLang[] = []
  for (const item of value) {
    if (typeof item === 'string' && isSpeechRecognitionLang(item) && !out.includes(item)) {
      out.push(item)
    }
  }
  return out.length ? out : [...DEFAULT_SPEECH_TARGETS]
}

export function readSpeechLangConfig(stored: {
  speechLang?: unknown
  speechLangMode?: unknown
  speechTargets?: unknown
  speechLangFixed?: unknown
}): SpeechLangConfig {
  const mode = stored.speechLangMode === 'fixed' ? 'fixed' : 'auto'
  const fixedRaw = typeof stored.speechLangFixed === 'string' ? stored.speechLangFixed : ''
  const fixed = isSpeechRecognitionLang(fixedRaw) ? fixedRaw : 'zh-CN'

  if (stored.speechLangMode === 'fixed' || stored.speechTargets != null) {
    const targets = normalizeSpeechTargets(stored.speechTargets)
    return {
      mode,
      targets: mode === 'fixed' ? [fixed] : targets,
      fixed,
    }
  }

  const legacy = stored.speechLang
  if (legacy === 'auto' || legacy == null) {
    return { ...DEFAULT_SPEECH_LANG_CONFIG }
  }
  if (typeof legacy === 'string' && isSpeechRecognitionLang(legacy)) {
    return { mode: 'fixed', targets: [legacy], fixed: legacy }
  }
  return { ...DEFAULT_SPEECH_LANG_CONFIG }
}

let cachedLastSpeechLang: string | null = null

export function getCachedLastSpeechLang(): string | null {
  return cachedLastSpeechLang
}

export function persistLastSpeechLang(lang: string): void {
  cachedLastSpeechLang = lang
  if (typeof chrome !== 'undefined' && chrome.storage?.local) {
    void chrome.storage.local.set({ [STORAGE.lastSpeechLang]: lang })
  }
}

export async function hydrateSpeechLangCache(): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) return
  const stored = await chrome.storage.local.get(STORAGE.lastSpeechLang)
  const value = stored[STORAGE.lastSpeechLang]
  cachedLastSpeechLang = typeof value === 'string' && value.trim() ? value.trim() : null
}

async function loadSpeechLangConfig(): Promise<SpeechLangConfig> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) {
    return { ...DEFAULT_SPEECH_LANG_CONFIG }
  }
  const stored = await chrome.storage.local.get([
    STORAGE.speechLang,
    STORAGE.speechLangMode,
    STORAGE.speechTargets,
    STORAGE.speechLangFixed,
  ])
  return readSpeechLangConfig(stored)
}

export async function persistSpeechLangConfig(config: SpeechLangConfig): Promise<void> {
  if (typeof chrome === 'undefined' || !chrome.storage?.local) return
  const targets = config.mode === 'fixed' ? [config.fixed] : normalizeSpeechTargets(config.targets)
  await chrome.storage.local.set({
    [STORAGE.speechLangMode]: config.mode,
    [STORAGE.speechTargets]: targets,
    [STORAGE.speechLangFixed]: config.fixed,
    [STORAGE.speechLang]: config.mode === 'auto' ? 'auto' : config.fixed,
  })
}

export function useSpeechLangSettings(): [
  SpeechLangConfig,
  (patch: Partial<SpeechLangConfig> | ((prev: SpeechLangConfig) => SpeechLangConfig)) => void,
] {
  const [config, setConfig] = useState<SpeechLangConfig>(DEFAULT_SPEECH_LANG_CONFIG)

  useEffect(() => {
    void hydrateSpeechLangCache()
    void loadSpeechLangConfig().then(setConfig)
    if (typeof chrome === 'undefined' || !chrome.storage?.onChanged) return
    const onChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ) => {
      if (area !== 'local') return
      if (
        changes[STORAGE.speechLangMode] ||
        changes[STORAGE.speechTargets] ||
        changes[STORAGE.speechLangFixed] ||
        changes[STORAGE.speechLang]
      ) {
        void loadSpeechLangConfig().then(setConfig)
      }
      if (changes[STORAGE.lastSpeechLang]) {
        const value = changes[STORAGE.lastSpeechLang].newValue
        cachedLastSpeechLang = typeof value === 'string' && value.trim() ? value.trim() : null
      }
    }
    chrome.storage.onChanged.addListener(onChange)
    return () => chrome.storage.onChanged.removeListener(onChange)
  }, [])

  const updateConfig = useCallback(
    (patch: Partial<SpeechLangConfig> | ((prev: SpeechLangConfig) => SpeechLangConfig)) => {
      setConfig((prev) => {
        const next = typeof patch === 'function' ? patch(prev) : { ...prev, ...patch }
        const normalized: SpeechLangConfig = {
          mode: next.mode === 'fixed' ? 'fixed' : 'auto',
          targets:
            next.mode === 'fixed'
              ? [isSpeechRecognitionLang(next.fixed) ? next.fixed : prev.fixed]
              : normalizeSpeechTargets(next.targets),
          fixed: isSpeechRecognitionLang(next.fixed) ? next.fixed : prev.fixed,
        }
        void persistSpeechLangConfig(normalized)
        return normalized
      })
    },
    []
  )

  return [config, updateConfig]
}

export function speechLangSelectValue(config: SpeechLangConfig): string {
  return config.mode === 'auto' ? 'auto' : config.fixed
}

export function speechLangConfigFromSelect(value: string, prev?: SpeechLangConfig): SpeechLangConfig {
  if (value === 'auto') {
    const base = prev ?? DEFAULT_SPEECH_LANG_CONFIG
    return {
      mode: 'auto',
      targets: base.mode === 'auto' ? [...base.targets] : [...DEFAULT_SPEECH_TARGETS],
      fixed: base.fixed,
    }
  }
  if (isSpeechRecognitionLang(value)) {
    return { mode: 'fixed', fixed: value, targets: [value] }
  }
  return prev ?? { ...DEFAULT_SPEECH_LANG_CONFIG }
}

export function speechLangShortLabel(config: SpeechLangConfig): string {
  if (config.mode === 'auto') return 'Auto'
  if (config.fixed === 'zh-CN') return '中'
  if (config.fixed === 'en-US') return 'EN'
  if (config.fixed === 'es-ES') return 'ES'
  if (config.fixed === 'ja-JP') return '日'
  if (config.fixed === 'ko-KR') return '한'
  return config.fixed
}

/** Composer quick toggle: Auto → 中文 → English → Auto */
export function cycleQuickSpeechLang(config: SpeechLangConfig): SpeechLangConfig {
  if (config.mode === 'auto') {
    return { mode: 'fixed', fixed: 'zh-CN', targets: ['zh-CN'] }
  }
  if (config.fixed === 'zh-CN') {
    return { mode: 'fixed', fixed: 'en-US', targets: ['en-US'] }
  }
  return { mode: 'auto', targets: [...DEFAULT_SPEECH_TARGETS], fixed: 'zh-CN' }
}

export function speechLangTitleKey(config: SpeechLangConfig): 'chat.voice.speechLangAuto' | 'chat.voice.speechLangZh' | 'chat.voice.speechLangEn' {
  if (config.mode === 'auto') return 'chat.voice.speechLangAuto'
  if (config.fixed === 'zh-CN') return 'chat.voice.speechLangZh'
  return 'chat.voice.speechLangEn'
}
