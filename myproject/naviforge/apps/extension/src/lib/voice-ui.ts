import { useCallback, useEffect, useState } from 'react'

import { STORAGE } from './settings'

export type VoiceUiMode = 'bar' | 'orb'

export const DEFAULT_VOICE_UI: VoiceUiMode = 'bar'

export function readVoiceUiMode(value: unknown): VoiceUiMode {
  return value === 'orb' ? 'orb' : 'bar'
}

export function useVoiceUiMode(): [VoiceUiMode, (next: VoiceUiMode) => void] {
  const [mode, setMode] = useState<VoiceUiMode>(DEFAULT_VOICE_UI)

  useEffect(() => {
    if (typeof chrome === 'undefined' || !chrome.storage?.local) return
    void chrome.storage.local.get(STORAGE.voiceUi).then((stored) => {
      setMode(readVoiceUiMode(stored[STORAGE.voiceUi]))
    })
    const onChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ) => {
      if (area !== 'local' || !changes[STORAGE.voiceUi]) return
      setMode(readVoiceUiMode(changes[STORAGE.voiceUi].newValue))
    }
    chrome.storage.onChanged.addListener(onChange)
    return () => chrome.storage.onChanged.removeListener(onChange)
  }, [])

  const setVoiceUiMode = useCallback((next: VoiceUiMode) => {
    setMode(next)
    if (typeof chrome !== 'undefined' && chrome.storage?.local) {
      void chrome.storage.local.set({ [STORAGE.voiceUi]: next })
    }
  }, [])

  return [mode, setVoiceUiMode]
}
