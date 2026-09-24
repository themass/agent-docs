import { STORAGE } from '../../lib/settings.js'
import type { GeniusFallPrefs } from './types.js'
import { listQuotaProviders } from './registry.js'

const DEFAULT_ENABLED = ['cursor']

export async function loadGeniusFallPrefs(): Promise<GeniusFallPrefs> {
  const saved = await chrome.storage.local.get(STORAGE.geniusFall)
  const raw = saved[STORAGE.geniusFall] as GeniusFallPrefs | undefined
  const known = new Set(listQuotaProviders().map((p) => p.id))
  const enabledIds = (raw?.enabledIds ?? DEFAULT_ENABLED).filter((id) => known.has(id))
  return { enabledIds: enabledIds.length ? enabledIds : DEFAULT_ENABLED }
}

export async function saveGeniusFallPrefs(prefs: GeniusFallPrefs): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.geniusFall]: prefs })
}

export async function setProviderEnabled(providerId: string, enabled: boolean): Promise<GeniusFallPrefs> {
  const prefs = await loadGeniusFallPrefs()
  const set = new Set(prefs.enabledIds)
  if (enabled) set.add(providerId)
  else set.delete(providerId)
  const next = { enabledIds: [...set] }
  await saveGeniusFallPrefs(next)
  return next
}
