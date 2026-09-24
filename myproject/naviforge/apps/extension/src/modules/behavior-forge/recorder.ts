import { attachNetwork, clearNetwork, listNetwork } from '../../lib/network-recorder.js'
import type { BehaviorEvent, BehaviorSessionRecord } from './types.js'
import type { eventWithTime } from './types.js'
import { summarizeNetworkEvents } from './network-summary.js'
import { loadBehaviorPrefs } from './prefs.js'
import { capEvents, deleteBehaviorSession, listBehaviorSessions, loadBehaviorSession, saveBehaviorSession } from './storage.js'
import { normalizeSessionEvents, replayDurationMs } from './replay-utils.js'

type LiveSession = {
  id: string
  tabId: number
  startedAt: number
  originUrl: string
  title: string
  events: BehaviorEvent[]
  rrwebEvents: eventWithTime[]
  captureDom: boolean
  viewport?: { w: number; h: number }
}

let live: LiveSession | null = null
const tabToSession = new Map<number, string>()

function sessionTitle(url: string): string {
  try {
    return new URL(url).hostname || 'Recording'
  } catch {
    return 'Recording'
  }
}

export function getLiveSessionId(): string | null {
  return live?.id ?? null
}

export function getLiveRecordingTabId(): number | null {
  return live?.tabId ?? null
}

export async function startBehaviorRecording(
  tabId: number,
  url: string,
  opts?: { captureDom?: boolean }
): Promise<string> {
  if (live) await stopBehaviorRecording()
  const prefs = await loadBehaviorPrefs()
  const captureDom = opts?.captureDom ?? prefs.captureDom
  const id = `bf_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
  live = {
    id,
    tabId,
    startedAt: Date.now(),
    originUrl: url,
    title: sessionTitle(url),
    events: [],
    rrwebEvents: [],
    captureDom,
  }
  tabToSession.set(tabId, id)
  clearNetwork(tabId)
  void attachNetwork(tabId).catch(() => {
    /* debugger may be blocked on chrome:// etc. */
  })
  await attachCaptureToTab(tabId, id, captureDom)
  await setRecordingTabBadge(tabId, true)
  return id
}

export async function stopBehaviorRecording(): Promise<BehaviorSessionRecord | null> {
  if (!live) return null
  const ended = live
  live = null
  tabToSession.delete(ended.tabId)
  await setRecordingTabBadge(ended.tabId, false)
  await detachCaptureFromTab(ended.tabId)

  const wallDurationMs = Date.now() - ended.startedAt
  const events = capEvents(normalizeSessionEvents(ended.events))
  let networkDigest
  try {
    const netEvents = listNetwork(ended.tabId, { limit: 200 })
    if (netEvents.length) networkDigest = summarizeNetworkEvents(netEvents, ended.startedAt)
  } catch {
    /* network plane optional */
  }
  const record: BehaviorSessionRecord = {
    id: ended.id,
    startedAt: new Date(ended.startedAt).toISOString(),
    endedAt: new Date().toISOString(),
    title: ended.title,
    originUrl: ended.originUrl,
    eventCount: events.length,
    durationMs: wallDurationMs,
    viewport: ended.viewport,
    events,
    hasRrweb: ended.rrwebEvents.length > 0,
    rrwebEventCount: ended.rrwebEvents.length || undefined,
    networkDigest,
  }
  record.durationMs = replayDurationMs(record)
  try {
    await saveBehaviorSession(record, ended.rrwebEvents)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(message)
  }
  return record
}

function getSessionTimeOffsetMs(): number {
  if (!live) return 0
  let maxT = 0
  for (const e of live.events) if (e.t > maxT) maxT = e.t
  return maxT
}

export function appendBehaviorEvents(sessionId: string, events: BehaviorEvent[]): void {
  if (!live || live.id !== sessionId) return
  if (!events.length) return
  const maxT = live.events.reduce((m, e) => Math.max(m, e.t), 0)
  const batchMin = Math.min(...events.map((e) => e.t))
  const shift = batchMin < maxT - 100 ? maxT - batchMin + 50 : 0
  const batch = shift ? events.map((e) => ({ ...e, t: e.t + shift })) : events
  live.events.push(...batch)
  const vp = batch.find((e) => e.kind === 'viewport')
  if (vp && vp.kind === 'viewport') {
    live.viewport = { w: vp.w, h: vp.h }
  }
}

export function appendRrwebEvents(sessionId: string, events: eventWithTime[]): void {
  if (!live || live.id !== sessionId || !events.length) return
  let maxTs = 0
  for (const e of live.rrwebEvents) if (e.timestamp > maxTs) maxTs = e.timestamp
  const batchMin = Math.min(...events.map((e) => e.timestamp))
  const shift = batchMin < maxTs - 100 ? maxTs - batchMin + 50 : 0
  const batch = shift ? events.map((e) => ({ ...e, timestamp: e.timestamp + shift })) : events
  live.rrwebEvents.push(...batch)
}

export async function onRecordingTabNavigated(tabId: number): Promise<void> {
  const sessionId = tabToSession.get(tabId)
  if (!sessionId || !live || live.id !== sessionId) return
  try {
    const tab = await chrome.tabs.get(tabId)
    if (tab.url) {
      live.originUrl = tab.url
      live.title = sessionTitle(tab.url)
    }
  } catch {
    /* tab gone */
  }
  await attachCaptureToTab(tabId, sessionId, live.captureDom)
  void import('./recording-hud-controller.js').then((m) => m.syncBehaviorRecordingHudOnTabUpdated(tabId))
}

async function setRecordingTabBadge(tabId: number, recording: boolean): Promise<void> {
  try {
    await chrome.action.setBadgeText({ tabId, text: recording ? '●' : '' })
    if (recording) await chrome.action.setBadgeBackgroundColor({ tabId, color: '#c9453a' })
  } catch {
    /* action API optional */
  }
}

async function attachCaptureToTab(tabId: number, sessionId: string, captureDom: boolean): Promise<void> {
  const timeOffsetMs = getSessionTimeOffsetMs()
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ['content-scripts/content.js'],
    })
  } catch {
    // already injected
  }
  await chrome.tabs.sendMessage(tabId, {
    type: 'PAGE_CONTROL',
    action: 'behavior_capture_start',
    payload: { sessionId, captureDom, timeOffsetMs },
    targetTabId: tabId,
  })
}

async function detachCaptureFromTab(tabId: number): Promise<void> {
  try {
    await chrome.tabs.sendMessage(tabId, {
      type: 'PAGE_CONTROL',
      action: 'behavior_capture_stop',
      payload: {},
      targetTabId: tabId,
    })
  } catch {
    // tab closed
  }
}

export async function handleBehaviorRecordMessage(
  message: Record<string, unknown>,
  sender: chrome.runtime.MessageSender
): Promise<unknown> {
  const action = message.action as string
  switch (action) {
    case 'start': {
      const tabId = typeof message.tabId === 'number' ? message.tabId : sender.tab?.id
      if (!tabId) return { ok: false, error: 'no tab' }
      const tab = await chrome.tabs.get(tabId)
      const captureDom =
        message.captureDom === true
          ? true
          : message.captureDom === false
            ? false
            : undefined
      const id = await startBehaviorRecording(tabId, tab.url ?? '', { captureDom })
      return { ok: true, sessionId: id }
    }
    case 'stop': {
      const record = await stopBehaviorRecording()
      return { ok: true, record }
    }
    case 'status':
      return {
        ok: true,
        recording: Boolean(live),
        sessionId: live?.id ?? null,
        eventCount: live?.events.length ?? 0,
        rrwebEventCount: live?.rrwebEvents.length ?? 0,
        captureDom: live?.captureDom ?? true,
        originUrl: live?.originUrl ?? null,
        pageTitle: live?.title ?? null,
      }
    case 'batch': {
      const sessionId = String(message.sessionId ?? '')
      const events = Array.isArray(message.events) ? (message.events as BehaviorEvent[]) : []
      appendBehaviorEvents(sessionId, events)
      return { ok: true }
    }
    case 'rrweb_batch': {
      const sessionId = String(message.sessionId ?? '')
      const events = Array.isArray(message.events) ? (message.events as eventWithTime[]) : []
      appendRrwebEvents(sessionId, events)
      return { ok: true }
    }
    case 'list':
      return { ok: true, sessions: await listBehaviorSessions() }
    case 'get': {
      const sessionId = String(message.sessionId ?? '')
      const record = await loadBehaviorSession(sessionId)
      return record ? { ok: true, record } : { ok: false, error: 'not found' }
    }
    case 'delete': {
      const sessionId = String(message.sessionId ?? '')
      await deleteBehaviorSession(sessionId)
      return { ok: true }
    }
    case 'mark_cloud': {
      const sessionId = String(message.sessionId ?? '')
      const cloudId = String(message.cloudId ?? '')
      const record = await loadBehaviorSession(sessionId)
      if (!record) return { ok: false, error: 'not found' }
      record.cloudId = cloudId
      await saveBehaviorSession(record)
      return { ok: true }
    }
    default:
      return { ok: false, error: 'unknown action' }
  }
}
