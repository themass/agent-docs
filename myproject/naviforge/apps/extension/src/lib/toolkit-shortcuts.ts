import type { ToolkitCatalogId } from './toolkit-catalog.js'

/**
 * chrome.commands names wired in background.ts.
 * Ids were renamed in 0.1.2: Chrome only applies suggested_key to a command
 * the first time that command appears. Renaming is how an update can assign
 * working defaults. Alt+letter (no Shift) is also swallowed on macOS because
 * Option+letter types a character (⌥S → ß) and never reaches the extension.
 */
export type ToolkitCommandId =
  | 'nf-open-toolkit'
  | 'nf-capture-visible'
  | 'nf-capture-full'
  | 'nf-screenshot-studio'
  | 'nf-translate'
  | 'nf-json-format'

export type ManifestSuggestedKey = {
  default: string
  mac: string
}

export type ToolkitShortcutRow = {
  command: ToolkitCommandId
  /** Popup / palette catalog id when the command maps to a toolkit tool */
  catalogId?: ToolkitCatalogId
  /** Shown in UI (Mac glyphs) */
  displayMac: string
  description: string
  /** Chrome allows at most four extension-wide suggested_key entries */
  manifestSuggested?: ManifestSuggestedKey
}

/**
 * Single source of truth for NaviForge browser shortcuts.
 * Manifest (wxt.config) must stay in sync via manifestCommands().
 */
export const TOOLKIT_SHORTCUT_ROWS: readonly ToolkitShortcutRow[] = [
  {
    command: 'nf-open-toolkit',
    catalogId: 'page-toollist',
    displayMac: '⌥⇧N',
    description: 'NaviForge: page tool list',
    manifestSuggested: { default: 'Alt+Shift+N', mac: 'Alt+Shift+N' },
  },
  {
    command: 'nf-capture-visible',
    catalogId: 'screenshot',
    displayMac: '⌥⇧A',
    description: 'NaviForge: visible screenshot',
    manifestSuggested: { default: 'Alt+Shift+A', mac: 'Alt+Shift+A' },
  },
  {
    command: 'nf-capture-full',
    catalogId: 'fullpage',
    displayMac: '⌥⇧S',
    description: 'NaviForge: full-page screenshot',
    manifestSuggested: { default: 'Alt+Shift+S', mac: 'Alt+Shift+S' },
  },
  {
    command: 'nf-screenshot-studio',
    catalogId: 'studio',
    displayMac: '⌘⇧S',
    description: 'NaviForge: screenshot studio',
    manifestSuggested: { default: 'Ctrl+Shift+S', mac: 'Command+Shift+S' },
  },
  {
    command: 'nf-translate',
    catalogId: 'translate',
    displayMac: '⌥⇧T',
    description: 'NaviForge: translate page',
    // Chrome allows four suggested_key values — translate bind once in chrome://extensions/shortcuts.
  },
  {
    command: 'nf-json-format',
    catalogId: 'json',
    displayMac: '',
    description: 'NaviForge: JSON format',
  },
] as const

export const CHROME_EXTENSION_SHORTCUTS_URL = 'chrome://extensions/shortcuts'

const DISPLAY_BY_CATALOG = new Map<ToolkitCatalogId, string>(
  TOOLKIT_SHORTCUT_ROWS.filter((row) => row.catalogId && row.displayMac).map((row) => [
    row.catalogId!,
    row.displayMac,
  ])
)

/** Shortcut glyph for catalog / options table (undefined = no default key). */
export function shortcutDisplayForCatalog(id: ToolkitCatalogId): string | undefined {
  const value = DISPLAY_BY_CATALOG.get(id)
  return value || undefined
}

/** Rows that ship a default key in manifest (max 4). */
export function manifestSuggestedShortcutRows(): ToolkitShortcutRow[] {
  return TOOLKIT_SHORTCUT_ROWS.filter((row) => row.manifestSuggested)
}

/** Build the `commands` block for wxt manifest. */
export function manifestCommands(): Record<
  string,
  { description: string; suggested_key?: ManifestSuggestedKey }
> {
  const out: Record<string, { description: string; suggested_key?: ManifestSuggestedKey }> = {}
  for (const row of TOOLKIT_SHORTCUT_ROWS) {
    out[row.command] = row.manifestSuggested
      ? { description: row.description, suggested_key: row.manifestSuggested }
      : { description: row.description }
  }
  return out
}

/** One-line summary for popup footer (Mac glyphs). */
export function popupShortcutsLine(locale: string): string {
  if (locale.startsWith('zh')) {
    return '⌥⇧N 工具浮层 · ⌥⇧A · ⌥⇧S · ⌘⇧S · ⌥⇧T（翻译需在扩展快捷键页绑定）'
  }
  if (locale.startsWith('es')) {
    return '⌥⇧N lista · ⌥⇧A · ⌥⇧S · ⌘⇧S · ⌥⇧T (traducir: enlazar en chrome://extensions/shortcuts)'
  }
  return '⌥⇧N tool list · ⌥⇧A · ⌥⇧S · ⌘⇧S · ⌥⇧T (bind translate in chrome://extensions/shortcuts)'
}

/** Options · toolkit panel shortcuts blurb. */
export function optionsShortcutsBody(locale: string): string {
  if (locale.startsWith('zh')) {
    return [
      '在普通 https 页使用（先点一下页面）：',
      '⌥⇧N 网页工具浮层',
      '⌥⇧A 可见截图 · ⌥⇧S 全页截图 · ⌘⇧S 截图工作室',
      '⌥⇧T 翻译 — 在扩展快捷键页为「translate」绑一次',
    ].join(' ')
  }
  if (locale.startsWith('es')) {
    return [
      'En una página https normal (haga clic en la página antes):',
      '⌥⇧N lista de herramientas',
      '⌥⇧A visible · ⌥⇧S página completa · ⌘⇧S estudio',
      '⌥⇧T traducir — enlazar en chrome://extensions/shortcuts',
    ].join(' ')
  }
  return [
    'On a normal https page (click the page first):',
    '⌥⇧N in-page tool list',
    '⌥⇧A visible · ⌥⇧S full page · ⌘⇧S studio',
    '⌥⇧T translate — bind once in chrome://extensions/shortcuts',
  ].join(' ')
}

export async function openExtensionShortcutsPage(): Promise<void> {
  await chrome.tabs.create({ url: CHROME_EXTENSION_SHORTCUTS_URL })
}
