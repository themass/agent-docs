import {
  DEFAULT_PRIVACY,
  STORAGE,
  trimActivities,
  type ActivityEntry,
  type PrivacySettings,
} from './settings'

export async function listActivities(): Promise<ActivityEntry[]> {
  const saved = await chrome.storage.local.get([STORAGE.activities, STORAGE.privacy])
  const activities = Array.isArray(saved[STORAGE.activities])
    ? (saved[STORAGE.activities] as ActivityEntry[])
    : []
  const privacy = {
    ...DEFAULT_PRIVACY,
    ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
  }
  return trimActivities(activities, privacy.retainHistoryDays)
}

export async function addActivity(
  entry: Omit<ActivityEntry, 'id' | 'createdAt'>
): Promise<ActivityEntry> {
  const next: ActivityEntry = {
    ...entry,
    id: crypto.randomUUID(),
    createdAt: Date.now(),
  }
  const saved = await chrome.storage.local.get(STORAGE.privacy)
  const privacy = {
    ...DEFAULT_PRIVACY,
    ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
  }
  if (privacy.retainHistoryDays === 0) return next
  const activities = [next, ...(await listActivities())].slice(0, 200)
  await chrome.storage.local.set({ [STORAGE.activities]: activities })
  return next
}

export async function updateActivity(
  id: string,
  patch: Pick<ActivityEntry, 'status'> & { detail?: string }
): Promise<void> {
  const activities = (await listActivities()).map((entry) =>
    entry.id === id ? { ...entry, ...patch } : entry
  )
  await chrome.storage.local.set({ [STORAGE.activities]: activities })
}

export async function appendActivityEvent(
  id: string,
  event: NonNullable<ActivityEntry['events']>[number]
): Promise<void> {
  const activities = (await listActivities()).map((entry) => {
    if (entry.id !== id) return entry
    return { ...entry, events: [...(entry.events ?? []), event].slice(-50) }
  })
  await chrome.storage.local.set({ [STORAGE.activities]: activities })
}
