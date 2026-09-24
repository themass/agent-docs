import { catalogs, type Messages } from './catalogs'
import { DEFAULT_LOCALE, type LocaleId } from './locales'

type Vars = Record<string, string | number>

function lookup(messages: Messages, key: string): string | undefined {
  let cur: unknown = messages
  for (const part of key.split('.')) {
    if (!cur || typeof cur !== 'object' || !(part in cur)) return undefined
    cur = (cur as Record<string, unknown>)[part]
  }
  return typeof cur === 'string' ? cur : undefined
}

function interpolate(text: string, vars?: Vars): string {
  if (!vars) return text
  let out = text
  for (const [name, value] of Object.entries(vars)) {
    out = out.replaceAll(`{${name}}`, String(value))
  }
  return out
}

let activeLocale: LocaleId = DEFAULT_LOCALE

export function setActiveLocale(locale: LocaleId): void {
  activeLocale = locale
}

export function getActiveLocale(): LocaleId {
  return activeLocale
}

export function t(key: string, vars?: Vars, locale: LocaleId = activeLocale): string {
  const text = lookup(catalogs[locale], key) ?? lookup(catalogs[DEFAULT_LOCALE], key) ?? key
  return interpolate(text, vars)
}
