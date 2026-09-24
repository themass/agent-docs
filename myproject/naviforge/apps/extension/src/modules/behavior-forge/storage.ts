import { STORAGE } from '../../lib/settings.js'
import type { BehaviorSessionMeta, BehaviorSessionRecord, eventWithTime } from './types.js'
import { deleteRrwebEvents, loadRrwebEvents, saveRrwebEvents } from './rrweb-storage.js'

const MAX_SESSIONS = 16
const MAX_EVENTS_PER_SESSION = 8_000

function isQuotaError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /quota|QuotaBytes/i.test(message)
}

export async function listBehaviorSessions(): Promise<BehaviorSessionMeta[]> {
  const saved = await chrome.storage.local.get(STORAGE.behaviorForgeIndex)
  const list = saved[STORAGE.behaviorForgeIndex]
  return Array.isArray(list) ? (list as BehaviorSessionMeta[]) : []
}

async function saveIndex(list: BehaviorSessionMeta[]): Promise<void> {
  const trimmed = list
    .sort((a, b) => b.startedAt.localeCompare(a.startedAt))
    .slice(0, MAX_SESSIONS)
  await chrome.storage.local.set({ [STORAGE.behaviorForgeIndex]: trimmed })
}

/** Drop oldest sessions (and rrweb blobs) to free chrome.storage quota. */
export async function pruneBehaviorSessions(keep = 6): Promise<number> {
  const list = await listBehaviorSessions()
  const sorted = [...list].sort((a, b) => b.startedAt.localeCompare(a.startedAt))
  const drop = sorted.slice(keep)
  for (const meta of drop) {
    await deleteBehaviorSession(meta.id)
  }
  return drop.length
}

export async function loadBehaviorSession(id: string): Promise<BehaviorSessionRecord | null> {
  const key = sessionKey(id)
  const saved = await chrome.storage.local.get(key)
  const raw = saved[key]
  if (!raw || typeof raw !== 'object') return null
  const record = raw as BehaviorSessionRecord
  if (record.hasRrweb) {
    const rrwebEvents = await loadRrwebEvents(id)
    if (rrwebEvents?.length) record.rrwebEvents = rrwebEvents
  }
  return record
}

function sessionKey(id: string): string {
  return `${STORAGE.behaviorForgeSession}:${id}`
}

export async function saveBehaviorSession(
  record: BehaviorSessionRecord,
  rrwebEvents?: eventWithTime[]
): Promise<void> {
  const events = record.events.slice(0, MAX_EVENTS_PER_SESSION)

  async function write(includeRrweb: boolean): Promise<{ rrwebCount: number }> {
    let rrwebCount = 0
    if (includeRrweb && rrwebEvents?.length) {
      rrwebCount = await saveRrwebEvents(record.id, rrwebEvents)
    } else if (!includeRrweb) {
      await deleteRrwebEvents(record.id)
    }
    const meta: BehaviorSessionMeta = {
      id: record.id,
      startedAt: record.startedAt,
      endedAt: record.endedAt,
      title: record.title,
      originUrl: record.originUrl,
      eventCount: events.length,
      durationMs: record.durationMs,
      viewport: record.viewport,
      hasRrweb: rrwebCount > 0,
      rrwebEventCount: rrwebCount || undefined,
      cloudId: record.cloudId,
      networkDigest: record.networkDigest,
    }
    await chrome.storage.local.set({
      [sessionKey(record.id)]: { ...meta, events },
    })
    const list = await listBehaviorSessions()
    const next = [meta, ...list.filter((s) => s.id !== record.id)]
    await saveIndex(next)
    record.hasRrweb = meta.hasRrweb
    record.rrwebEventCount = meta.rrwebEventCount
    return { rrwebCount }
  }

  try {
    await write(true)
    return
  } catch (error) {
    if (!isQuotaError(error)) throw error
  }

  await pruneBehaviorSessions(4)

  try {
    await write(true)
    return
  } catch (error) {
    if (!isQuotaError(error)) throw error
  }

  // ponytail: trail-only beats losing the whole session when DOM replay is too large
  await write(false)
}

export async function deleteBehaviorSession(id: string): Promise<void> {
  await chrome.storage.local.remove(sessionKey(id))
  await deleteRrwebEvents(id)
  const list = await listBehaviorSessions()
  await saveIndex(list.filter((s) => s.id !== id))
}

export function capEvents<T>(events: T[]): T[] {
  return events.length > MAX_EVENTS_PER_SESSION ? events.slice(-MAX_EVENTS_PER_SESSION) : events
}
