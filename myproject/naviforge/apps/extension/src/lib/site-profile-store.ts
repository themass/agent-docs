import { BUNDLED_PROFILES, type SiteProfile } from './content-extract'
import { safeStorageLocalGet, safeStorageLocalSet } from './extension-runtime'

const KEY = 'naviforgeSiteProfiles'

/** Learned and user-authored profiles only — bundled ones ship with the code. */
export async function listLearnedProfiles(): Promise<SiteProfile[]> {
  const saved = await safeStorageLocalGet(KEY)
  const list = saved?.[KEY] as SiteProfile[] | undefined
  return Array.isArray(list) ? list : []
}

/** Resolution order: user > learned > bundled. */
export async function listProfiles(): Promise<SiteProfile[]> {
  const learned = await listLearnedProfiles()
  return [
    ...learned.filter((profile) => profile.source === 'user'),
    ...learned.filter((profile) => profile.source !== 'user'),
    ...BUNDLED_PROFILES,
  ]
}

export async function saveProfile(profile: SiteProfile): Promise<void> {
  const list = await listLearnedProfiles()
  const index = list.findIndex((item) => item.id === profile.id)
  if (index >= 0) list[index] = profile
  else list.unshift(profile)
  await safeStorageLocalSet({ [KEY]: list.slice(0, 100) })
}

export async function deleteProfile(id: string): Promise<void> {
  const list = (await listLearnedProfiles()).filter((item) => item.id !== id)
  await safeStorageLocalSet({ [KEY]: list })
}

/**
 * Persist a freshly induced profile, but never overwrite a bundled or
 * user-authored one — a page that renders oddly must not poison a good rule.
 */
export async function rememberProfile(proposed: SiteProfile | undefined): Promise<boolean> {
  if (!proposed) return false
  if (BUNDLED_PROFILES.some((profile) => profile.id === proposed.id)) return false
  const existing = await listLearnedProfiles()
  const current = existing.find((item) => item.id === proposed.id)
  if (current?.source === 'user') return false
  if (current?.detailUrl === proposed.detailUrl) return false
  await saveProfile(proposed)
  return true
}
