import { STORAGE } from './settings'

/** Store listing default: BYOK. When true, show Account / NewAPI managed login. */
export async function isManagedLoginEnabled(): Promise<boolean> {
  const saved = await chrome.storage.local.get(STORAGE.managedLoginEnabled)
  return saved[STORAGE.managedLoginEnabled] === true
}

export async function setManagedLoginEnabled(enabled: boolean): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.managedLoginEnabled]: enabled })
}
