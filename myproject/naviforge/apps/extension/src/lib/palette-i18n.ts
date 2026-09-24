import { loadResolvedLocale } from '../i18n/I18nProvider'
import { setActiveLocale, t } from '../i18n/t'
import {
  popupI18nKey,
  type ToolkitCatalogId,
  type ToolkitCatalogItem,
} from './toolkit-catalog'

const SECTION_KEYS: Record<ToolkitCatalogItem['section'], string> = {
  quick: 'sectionQuick',
  capture: 'sectionCapture',
  page: 'sectionPage',
  utility: 'sectionUtility',
  nav: 'sectionNav',
}

export async function initPaletteI18n(): Promise<void> {
  const locale = await loadResolvedLocale()
  setActiveLocale(locale)
}

export function toolkitI18n(id: ToolkitCatalogId): { label: string; hint: string } {
  const key = popupI18nKey(id)
  return {
    label: t(`popup.${key}`),
    hint: t(`popup.${key}Hint`),
  }
}

export function toolkitSectionLabel(section: ToolkitCatalogItem['section']): string {
  return t(`popup.${SECTION_KEYS[section]}`)
}

export function paletteSearchPlaceholder(): string {
  return t('palette.search')
}

export function paletteFooterKeys(): string {
  return t('palette.footerKeys')
}

export function paletteFooterHint(): string {
  return t('palette.footerHint')
}
