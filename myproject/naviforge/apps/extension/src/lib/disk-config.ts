import { ensureLocalHelper, workspaceRpc } from './local-workspace'
import {
  DEFAULT_PRIVACY,
  DEFAULT_WEB_SEARCH,
  STORAGE,
  readWebSearchSettings,
  type PrivacySettings,
  type WebSearchSettings,
} from './settings'
import {
  applyModifyHeaderRules,
  DEFAULT_MODIFY_HEADERS,
  normalizeModifyHeaders,
  type ModifyHeadersSettings,
} from './modify-headers'
import { loadModelProfiles } from './llm-profiles'

/** Paths under ~/NaviForge. Disk is source of truth when the helper is up. */
export const DISK_PATHS = {
  models: 'config/models.json',
  search: 'config/search.json',
  settings: 'config/settings.json',
} as const

export type DiskSettingsFile = {
  privacy: PrivacySettings
  headers: ModifyHeadersSettings
}

export async function readWorkspaceJson<T>(rel: string): Promise<T | null> {
  const helper = await ensureLocalHelper()
  if (!helper.ok) return null
  try {
    const { content } = await workspaceRpc<{ content: string }>('read', { path: rel })
    if (!content.trim()) return null
    return JSON.parse(content) as T
  } catch {
    return null
  }
}

export async function writeWorkspaceJson(rel: string, value: unknown): Promise<boolean> {
  const helper = await ensureLocalHelper()
  if (!helper.ok) return false
  try {
    await workspaceRpc('write', { path: rel, content: `${JSON.stringify(value, null, 2)}\n` })
    return true
  } catch {
    return false
  }
}

/** Disk wins on helper connect / restart; missing files are seeded from chrome.storage. */
export async function hydrateDiskConfig(): Promise<void> {
  const helper = await ensureLocalHelper()
  if (!helper.ok) return
  const saved = await chrome.storage.local.get([
    STORAGE.webSearch,
    STORAGE.privacy,
    STORAGE.modifyHeaders,
  ])

  await loadModelProfiles()

  const diskSearch = await readWorkspaceJson<unknown>(DISK_PATHS.search)
  if (diskSearch && typeof diskSearch === 'object') {
    await chrome.storage.local.set({ [STORAGE.webSearch]: readWebSearchSettings(diskSearch) })
  } else if (saved[STORAGE.webSearch]) {
    await writeWorkspaceJson(DISK_PATHS.search, readWebSearchSettings(saved[STORAGE.webSearch]))
  } else {
    await writeWorkspaceJson(DISK_PATHS.search, DEFAULT_WEB_SEARCH)
  }

  const diskSettings = await readWorkspaceJson<Partial<DiskSettingsFile>>(DISK_PATHS.settings)
  const privacy = {
    ...DEFAULT_PRIVACY,
    ...((diskSettings?.privacy ?? saved[STORAGE.privacy]) as Partial<PrivacySettings> | undefined),
  }
  const headers = normalizeModifyHeaders(diskSettings?.headers ?? saved[STORAGE.modifyHeaders])
  await chrome.storage.local.set({
    [STORAGE.privacy]: privacy,
    [STORAGE.modifyHeaders]: headers,
  })
  if (!diskSettings?.privacy && !diskSettings?.headers) {
    await writeWorkspaceJson(DISK_PATHS.settings, { privacy, headers })
  }
  await applyModifyHeaderRules(headers).catch(() => {})
}

export async function persistDiskSettings(patch: {
  privacy?: PrivacySettings
  headers?: ModifyHeadersSettings
}): Promise<void> {
  const saved = await chrome.storage.local.get([STORAGE.privacy, STORAGE.modifyHeaders])
  const current = (await readWorkspaceJson<Partial<DiskSettingsFile>>(DISK_PATHS.settings)) ?? {}
  const privacy = patch.privacy ?? current.privacy ?? (saved[STORAGE.privacy] as PrivacySettings) ?? DEFAULT_PRIVACY
  const headers =
    patch.headers ??
    current.headers ??
    normalizeModifyHeaders(saved[STORAGE.modifyHeaders]) ??
    DEFAULT_MODIFY_HEADERS
  await writeWorkspaceJson(DISK_PATHS.settings, { privacy, headers })
}

/** Mirror chrome.storage keys that belong on disk. */
export async function syncDiskConfigFromPartial(values: Record<string, unknown>): Promise<void> {
  if (STORAGE.llmProfiles in values && values[STORAGE.llmProfiles]) {
    await writeWorkspaceJson(DISK_PATHS.models, values[STORAGE.llmProfiles])
  }
  if (STORAGE.webSearch in values) {
    await writeWorkspaceJson(DISK_PATHS.search, readWebSearchSettings(values[STORAGE.webSearch]))
  }
  if (STORAGE.privacy in values || STORAGE.modifyHeaders in values) {
    await persistDiskSettings({
      privacy: values[STORAGE.privacy] as PrivacySettings | undefined,
      headers: values[STORAGE.modifyHeaders] as ModifyHeadersSettings | undefined,
    })
  }
}
