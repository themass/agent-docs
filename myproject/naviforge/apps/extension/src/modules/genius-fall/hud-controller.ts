import { STORAGE } from '../../lib/settings.js'
import { snapshotCurrentWebTab } from '../../lib/toolkit-actions.js'
import { DEFAULT_HUD_PREFS, type GeniusFallHudPrefs } from './hud-types.js'
import { fetchGeniusFallHudState } from './hud-service.js'
import { ensureContentScript } from '../../lib/ensure-content-script.js'

const HUD_MSG = 'GENIUS_FALL_HUD' as const

type GlobalHud = { visible: boolean; tabId: number | null }

export async function loadHudPrefs(): Promise<GeniusFallHudPrefs> {
  const saved = await chrome.storage.local.get(STORAGE.geniusFallHud)
  const raw = saved[STORAGE.geniusFallHud] as Partial<GeniusFallHudPrefs> | undefined
  return {
    x: typeof raw?.x === 'number' ? raw.x : DEFAULT_HUD_PREFS.x,
    y: typeof raw?.y === 'number' ? raw.y : DEFAULT_HUD_PREFS.y,
    collapsed: Boolean(raw?.collapsed),
    scale:
      typeof raw?.scale === 'number'
        ? Math.min(1.35, Math.max(0.55, raw.scale))
        : DEFAULT_HUD_PREFS.scale,
    heightScale:
      typeof raw?.heightScale === 'number'
        ? Math.min(1.35, Math.max(0.65, raw.heightScale))
        : DEFAULT_HUD_PREFS.heightScale,
    bgColor: typeof raw?.bgColor === 'string' ? raw.bgColor : DEFAULT_HUD_PREFS.bgColor,
    bgOpacity:
      typeof raw?.bgOpacity === 'number'
        ? Math.min(1, Math.max(0.2, raw.bgOpacity))
        : DEFAULT_HUD_PREFS.bgOpacity,
    title: typeof raw?.title === 'string' && raw.title.trim() ? raw.title.trim() : DEFAULT_HUD_PREFS.title,
  }
}

async function loadGlobalHud(): Promise<GlobalHud> {
  const saved = await chrome.storage.local.get(STORAGE.geniusFallHudGlobal)
  const raw = saved[STORAGE.geniusFallHudGlobal] as Partial<GlobalHud> | undefined
  return {
    visible: Boolean(raw?.visible),
    tabId: typeof raw?.tabId === 'number' ? raw.tabId : null,
  }
}

async function setGlobalHud(next: GlobalHud): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.geniusFallHudGlobal]: next })
}

export async function saveHudPosition(x: number, y: number): Promise<void> {
  const prefs = await loadHudPrefs()
  await chrome.storage.local.set({ [STORAGE.geniusFallHud]: { ...prefs, x, y } })
}

export async function saveHudPrefs(patch: Partial<GeniusFallHudPrefs>): Promise<GeniusFallHudPrefs> {
  const prefs = await loadHudPrefs()
  const next = { ...prefs, ...patch }
  await chrome.storage.local.set({ [STORAGE.geniusFallHud]: next })
  return next
}

async function sendTabHud(tabId: number, action: string, payload: Record<string, unknown> = {}): Promise<unknown> {
  const ensured = await ensureContentScript(tabId)
  if (!ensured.ok) throw new Error(ensured.error ?? '无法注入页面脚本')
  return chrome.tabs.sendMessage(tabId, {
    type: 'PAGE_CONTROL',
    action,
    payload,
    targetTabId: tabId,
  })
}

async function hideHudOnAllTabs(): Promise<void> {
  await hideHudOnAllTabsExcept(undefined)
}

async function hideHudOnAllTabsExcept(keepTabId?: number): Promise<void> {
  const tabs = await chrome.tabs.query({})
  await Promise.all(
    tabs.map((tab) => {
      if (!tab.id || tab.id === keepTabId) return undefined
      return sendTabHud(tab.id, 'genius_fall_hud_hide', {}).catch(() => undefined)
    })
  )
}

function loadingState(): import('./hud-types.js').GeniusFallHudState {
  return {
    ok: false,
    loading: true,
    label: 'CURSOR',
    spentUsd: null,
    limitUsd: null,
    percentUsed: null,
    remainingUsd: null,
    cycleEnd: null,
    teamPercent: null,
    updatedAt: null,
  }
}

async function ensureShowHudOnTab(tabId: number): Promise<void> {
  const prefs = await loadHudPrefs()
  const state = loadingState()
  await sendTabHud(tabId, 'genius_fall_hud_ensure', { state, prefs })
  void fetchGeniusFallHudState()
    .then(() => refreshGeniusFallHudOnTab(tabId))
    .catch((error) => {
      const errState: import('./hud-types.js').GeniusFallHudState = {
        ...loadingState(),
        loading: false,
        error: error instanceof Error ? error.message : String(error),
      }
      void sendTabHud(tabId, 'genius_fall_hud_update', { state: errState })
    })
}

export async function resolveGeniusFallHudTab(explicitTabId?: number): Promise<number | null> {
  if (explicitTabId != null) {
    try {
      const tab = await chrome.tabs.get(explicitTabId)
      if (tab.id != null) return tab.id
    } catch {
      /* closed */
    }
  }
  const tab = await snapshotCurrentWebTab()
  return tab?.id ?? null
}

export async function toggleGeniusFallHudOnTab(
  tabId: number
): Promise<{ visible: boolean; error?: string }> {
  const global = await loadGlobalHud()
  if (global.visible && global.tabId === tabId) {
    await setGlobalHud({ visible: false, tabId: null })
    await hideGeniusFallHudOnTab(tabId).catch(() => undefined)
    return { visible: false }
  }
  return openGeniusFallHudOnTab(tabId)
}

/** Idempotent show — used by popup so a failed prior attempt does not flip to "hide". */
export async function openGeniusFallHudOnTab(
  tabId: number
): Promise<{ visible: true }> {
  try {
    await hideHudOnAllTabsExcept(tabId)
    const prefs = await loadHudPrefs()
    await sendTabHud(tabId, 'genius_fall_hud_ensure', {
      state: loadingState(),
      prefs,
    })
    await setGlobalHud({ visible: true, tabId })
    void fetchGeniusFallHudState()
      .then(() => refreshGeniusFallHudOnTab(tabId))
      .catch((error) => {
        const errState: import('./hud-types.js').GeniusFallHudState = {
          ...loadingState(),
          loading: false,
          error: error instanceof Error ? error.message : String(error),
        }
        void sendTabHud(tabId, 'genius_fall_hud_update', { state: errState })
      })
    return { visible: true }
  } catch (error) {
    await setGlobalHud({ visible: false, tabId: null })
    throw error
  }
}

/** Follow active tab when global HUD is on. */
export async function syncGeniusFallHudFollowActiveTab(tabId: number): Promise<void> {
  const global = await loadGlobalHud()
  if (!global.visible) return
  if (global.tabId === tabId) return
  try {
    const tab = await chrome.tabs.get(tabId)
    if (!tab.url || !/^https?:/i.test(tab.url)) return
  } catch {
    return
  }
  await setGlobalHud({ visible: true, tabId })
  await hideHudOnAllTabsExcept(tabId)
  await ensureShowHudOnTab(tabId)
}

export async function closeGeniusFallHudGlobal(): Promise<void> {
  const global = await loadGlobalHud()
  if (!global.visible) return
  await setGlobalHud({ visible: false, tabId: null })
  await hideHudOnAllTabs()
}

export async function refreshGeniusFallHudOnTab(tabId: number): Promise<void> {
  const state = await fetchGeniusFallHudState()
  await sendTabHud(tabId, 'genius_fall_hud_update', { state })
}

export async function hideGeniusFallHudOnTab(tabId: number): Promise<void> {
  await sendTabHud(tabId, 'genius_fall_hud_hide', {})
}

export { HUD_MSG }
