import { STORAGE, DEFAULT_PRIVACY, normalizePrivacySettings, type PrivacySettings } from './settings'

/** Merge, normalize, and persist privacy — syncs chat + options via storage listener. */
export async function patchPrivacySettings(
  patch: Partial<PrivacySettings>
): Promise<PrivacySettings> {
  const saved = await chrome.storage.local.get(STORAGE.privacy)
  const merged = {
    ...DEFAULT_PRIVACY,
    ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
    ...patch,
  } as PrivacySettings
  const { privacy, changed } = normalizePrivacySettings(merged)
  if (changed || patch) {
    await chrome.storage.local.set({ [STORAGE.privacy]: privacy })
  }
  return privacy
}
