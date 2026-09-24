/**
 * Add a UI language:
 * 1. append here
 * 2. `catalogs/<id>.ts` with `satisfies Messages`
 * 3. register in `catalogs/index.ts`
 * 4. `packages/runtime/src/ui-copy.ts` (HITL / acting / privacy — runtime cannot import the extension)
 * 5. `public/_locales/<chrome_id>/messages.json` for the store listing
 * Chrome folders use `zh_CN` (underscore); in-app id is `zh-CN`.
 */
export const LOCALES = ['en', 'zh-CN', 'es'] as const
export type LocaleId = (typeof LOCALES)[number]
export type LocalePreference = 'auto' | LocaleId

export const DEFAULT_LOCALE: LocaleId = 'en'

export const LOCALE_LABELS: Record<LocalePreference, string> = {
  auto: 'Auto',
  en: 'English',
  'zh-CN': '简体中文',
  es: 'Español',
}

export function isLocaleId(value: string): value is LocaleId {
  return (LOCALES as readonly string[]).includes(value)
}

export function isLocalePreference(value: unknown): value is LocalePreference {
  return value === 'auto' || (typeof value === 'string' && isLocaleId(value))
}

/** Map browser / Chrome UI language tags onto a shipped catalog. */
export function resolveLocale(preference: LocalePreference, languages: readonly string[]): LocaleId {
  if (preference !== 'auto') return preference
  for (const raw of languages) {
    const tag = raw.trim().toLowerCase().replace(/_/g, '-')
    if (!tag) continue
    if (tag === 'zh' || tag.startsWith('zh-')) return 'zh-CN'
    if (tag === 'es' || tag.startsWith('es-')) return 'es'
    if (tag === 'en' || tag.startsWith('en-')) return 'en'
  }
  return DEFAULT_LOCALE
}

/** Initial UI locale before React mounts (does not touch document.lang — avoids IME hijack). */
export function bootstrapDocumentLang(): LocaleId {
  return resolveLocale('auto', browserLanguages())
}

export function browserLanguages(): string[] {
  const langs: string[] = []
  try {
    const ui = globalThis.chrome?.i18n?.getUILanguage?.()
    if (ui) langs.push(ui)
  } catch {
    /* ignore */
  }
  if (typeof navigator !== 'undefined') {
    langs.push(...(navigator.languages ?? []), navigator.language)
  }
  return langs.filter(Boolean)
}
