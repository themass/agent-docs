import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { STORAGE } from '../lib/settings'
import {
  browserLanguages,
  isLocalePreference,
  resolveLocale,
  bootstrapDocumentLang,
  type LocaleId,
  type LocalePreference,
} from './locales'
import { setActiveLocale, t as translate } from './t'
import { guardDocumentLang } from '../lib/ime-safe-surface'

export type I18nValue = {
  locale: LocaleId
  preference: LocalePreference
  t: typeof translate
  setPreference: (next: LocalePreference) => void
}

const I18nContext = createContext<I18nValue | null>(null)

export async function loadLocalePreference(): Promise<LocalePreference> {
  const stored = await chrome.storage.local.get(STORAGE.locale)
  const value = stored[STORAGE.locale]
  return isLocalePreference(value) ? value : 'auto'
}

export async function loadResolvedLocale(): Promise<LocaleId> {
  const preference = await loadLocalePreference()
  return resolveLocale(preference, browserLanguages())
}

function applyLocale(locale: LocaleId): void {
  setActiveLocale(locale)
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [preference, setPreferenceState] = useState<LocalePreference>('auto')
  const [locale, setLocale] = useState<LocaleId>(() => bootstrapDocumentLang())

  useEffect(() => {
    applyLocale(locale)
    const stopLangGuard = guardDocumentLang()
    let cancelled = false
    void loadLocalePreference().then((pref) => {
      if (cancelled) return
      const resolved = resolveLocale(pref, browserLanguages())
      setPreferenceState(pref)
      setLocale(resolved)
      applyLocale(resolved)
    })
    const onChange = (changes: Record<string, chrome.storage.StorageChange>, area: string): void => {
      if (area !== 'local' || !changes[STORAGE.locale]) return
      const value = changes[STORAGE.locale].newValue
      const pref: LocalePreference = isLocalePreference(value) ? value : 'auto'
      const resolved = resolveLocale(pref, browserLanguages())
      setPreferenceState(pref)
      setLocale(resolved)
      applyLocale(resolved)
    }
    chrome.storage.onChanged.addListener(onChange)
    return () => {
      cancelled = true
      stopLangGuard()
      chrome.storage.onChanged.removeListener(onChange)
    }
  }, [])

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      preference,
      t: (key, vars) => translate(key, vars, locale),
      setPreference(next) {
        void chrome.storage.local.set({ [STORAGE.locale]: next })
        const resolved = resolveLocale(next, browserLanguages())
        setPreferenceState(next)
        setLocale(resolved)
        applyLocale(resolved)
      },
    }),
    [locale, preference]
  )

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext)
  if (!ctx) throw new Error('useI18n requires I18nProvider')
  return ctx
}
