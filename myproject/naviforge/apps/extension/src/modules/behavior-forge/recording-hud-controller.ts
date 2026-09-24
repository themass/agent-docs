import { ensureContentScript } from '../../lib/ensure-content-script.js'
import { STORAGE } from '../../lib/settings.js'
import { behaviorRecord } from './api.js'
import { getLiveRecordingTabId } from './recorder.js'
import { loadRecordingHudCopy } from './recording-hud-copy.js'
import type { RecordingHudPhase } from './recording-hud.js'

export type BehaviorRecordingHudGlobal = {
  visible: boolean
  tabId: number | null
  phase: RecordingHudPhase
  savedCount?: number | null
  error?: string
  posX?: number | null
  posY?: number | null
}

type TabSync = {
  timer?: ReturnType<typeof setTimeout>
  inflight?: Promise<void>
}

const tabSync = new Map<number, TabSync>()
const SYNC_DEBOUNCE_MS = 400

async function loadGlobal(): Promise<BehaviorRecordingHudGlobal> {
  const saved = await chrome.storage.local.get(STORAGE.behaviorRecordingHudGlobal)
  const raw = saved[STORAGE.behaviorRecordingHudGlobal] as Partial<BehaviorRecordingHudGlobal> | undefined
  return {
    visible: Boolean(raw?.visible),
    tabId: typeof raw?.tabId === 'number' ? raw.tabId : null,
    phase: raw?.phase ?? 'idle',
    savedCount: raw?.savedCount ?? null,
    error: typeof raw?.error === 'string' ? raw.error : undefined,
    posX: typeof raw?.posX === 'number' ? raw.posX : null,
    posY: typeof raw?.posY === 'number' ? raw.posY : null,
  }
}

export async function patchBehaviorRecordingHudGlobal(
  patch: Partial<BehaviorRecordingHudGlobal>
): Promise<BehaviorRecordingHudGlobal> {
  const current = await loadGlobal()
  const next = { ...current, ...patch }
  await chrome.storage.local.set({ [STORAGE.behaviorRecordingHudGlobal]: next })
  return next
}

async function sendShow(tabId: number, global: BehaviorRecordingHudGlobal): Promise<void> {
  const ensured = await ensureContentScript(tabId)
  if (!ensured.ok) throw new Error(ensured.error ?? 'inject failed')

  const copy = await loadRecordingHudCopy()
  const status = await behaviorRecord<{
    recording?: boolean
    eventCount?: number
    originUrl?: string
    pageTitle?: string
  }>('status')

  const tab = await chrome.tabs.get(tabId).catch(() => null)
  const recording = Boolean(status.recording)
  let phase: RecordingHudPhase = global.phase
  if (recording) {
    phase = 'recording'
  } else if (global.phase === 'saved' || global.phase === 'error' || global.phase === 'saving') {
    phase = global.phase
  } else if (phase === 'recording' || phase === 'saving') {
    if (global.savedCount != null) phase = 'saved'
    else if (global.error) phase = 'error'
    else phase = 'idle'
  }

  const pageUrl = status.originUrl ?? tab?.url ?? ''
  const pageTitle = status.pageTitle ?? tab?.title ?? ''

  await chrome.tabs.sendMessage(tabId, {
    type: 'PAGE_CONTROL',
    action: 'behavior_recording_hud_show',
    payload: {
      copy,
      pos: global.posX != null && global.posY != null ? { x: global.posX, y: global.posY } : null,
      state: {
        phase,
        recording,
        eventCount: status.eventCount ?? 0,
        savedCount: global.savedCount ?? null,
        error: global.error,
        pageUrl,
        pageTitle,
      },
    },
    targetTabId: tabId,
  })
}

async function reshowHud(tabId: number): Promise<void> {
  const global = await loadGlobal()
  if (!global.visible) return
  for (let i = 0; i < 2; i++) {
    try {
      await sendShow(tabId, global)
      return
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 200 * (i + 1)))
    }
  }
}

function scheduleReshow(tabId: number): void {
  let entry = tabSync.get(tabId)
  if (!entry) {
    entry = {}
    tabSync.set(tabId, entry)
  }
  if (entry.timer) clearTimeout(entry.timer)
  entry.timer = setTimeout(() => {
    entry!.timer = undefined
    if (entry!.inflight) return
    entry!.inflight = reshowHud(tabId).finally(() => {
      entry!.inflight = undefined
    })
  }, SYNC_DEBOUNCE_MS)
}

export async function showBehaviorRecordingHudOnTab(
  tabId: number,
  opts?: { fresh?: boolean }
): Promise<{ ok: boolean; error?: string }> {
  try {
    const current = await loadGlobal()
    const keepUi = !opts?.fresh && current.visible && current.tabId === tabId
    const global = await patchBehaviorRecordingHudGlobal({
      visible: true,
      tabId,
      phase: keepUi ? current.phase : opts?.fresh ? current.phase : 'idle',
      savedCount: keepUi || opts?.fresh ? current.savedCount : null,
      error: keepUi || opts?.fresh ? current.error : undefined,
      posX: keepUi || opts?.fresh ? current.posX : null,
      posY: keepUi || opts?.fresh ? current.posY : null,
    })
    await sendShow(tabId, global)
    return { ok: true }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : String(error) }
  }
}

export async function openBehaviorRecordingHudOnTab(
  tabId: number
): Promise<{ ok: boolean; error?: string }> {
  return showBehaviorRecordingHudOnTab(tabId, { fresh: true })
}

export async function closeBehaviorRecordingHudGlobal(): Promise<void> {
  const global = await loadGlobal()
  if (!global.visible) return
  await patchBehaviorRecordingHudGlobal({
    visible: false,
    tabId: null,
    phase: 'idle',
    savedCount: null,
    error: undefined,
  })
  if (global.tabId != null) {
    try {
      await chrome.tabs.sendMessage(global.tabId, {
        type: 'PAGE_CONTROL',
        action: 'behavior_recording_hud_hide',
        payload: {},
        targetTabId: global.tabId,
      })
    } catch {
      /* tab closed */
    }
  }
}

/** Re-inject HUD after same-tab navigation while panel is open. */
export async function syncBehaviorRecordingHudOnTabUpdated(tabId: number): Promise<void> {
  const recordingTabId = getLiveRecordingTabId()
  if (recordingTabId === tabId) {
    try {
      const tab = await chrome.tabs.get(tabId)
      if (!tab.url || !/^https?:/i.test(tab.url)) return
    } catch {
      return
    }
    await patchBehaviorRecordingHudGlobal({
      visible: true,
      tabId,
      phase: 'recording',
      savedCount: null,
      error: undefined,
    })
    scheduleReshow(tabId)
    return
  }

  const global = await loadGlobal()
  if (!global.visible) return

  const targetTab = recordingTabId ?? global.tabId
  if (targetTab !== tabId) return

  try {
    const tab = await chrome.tabs.get(tabId)
    if (!tab.url || !/^https?:/i.test(tab.url)) return
  } catch {
    return
  }

  if (global.tabId !== tabId) {
    void patchBehaviorRecordingHudGlobal({ tabId })
  }
  scheduleReshow(tabId)
}
