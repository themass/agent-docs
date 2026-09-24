import type { LocaleId } from '../locales'
import { en, type Messages } from './en'
import { es } from './es'
import { zhCN } from './zh-CN'

export type { Messages }

/** Register a new catalog here after adding `LOCALES` and the file. */
export const catalogs: Record<LocaleId, Messages> = {
  en,
  'zh-CN': zhCN,
  es,
}
