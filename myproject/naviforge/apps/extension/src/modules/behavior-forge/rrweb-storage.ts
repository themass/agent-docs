import { STORAGE } from '../../lib/settings.js'
import type { eventWithTime } from './types.js'

const MAX_RRWEB_EVENTS = 2_500

function rrwebKey(id: string): string {
  return `${STORAGE.behaviorForgeRrweb}:${id}`
}

export function capRrwebEvents(events: eventWithTime[]): eventWithTime[] {
  if (events.length <= MAX_RRWEB_EVENTS) return events
  return events.slice(-MAX_RRWEB_EVENTS)
}

export async function saveRrwebEvents(id: string, events: eventWithTime[]): Promise<number> {
  const capped = capRrwebEvents(events)
  if (!capped.length) return 0
  await chrome.storage.local.set({ [rrwebKey(id)]: capped })
  return capped.length
}

export async function loadRrwebEvents(id: string): Promise<eventWithTime[] | null> {
  const saved = await chrome.storage.local.get(rrwebKey(id))
  const raw = saved[rrwebKey(id)]
  return Array.isArray(raw) ? (raw as eventWithTime[]) : null
}

export async function deleteRrwebEvents(id: string): Promise<void> {
  await chrome.storage.local.remove(rrwebKey(id))
}
