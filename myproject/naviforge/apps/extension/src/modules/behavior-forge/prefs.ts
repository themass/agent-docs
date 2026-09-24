import { STORAGE } from '../../lib/settings.js'
import {
  BEHAVIOR_PREFS_VERSION,
  DEFAULT_BEHAVIOR_PREFS,
  type BehaviorPrefs,
} from './types.js'

export async function loadBehaviorPrefs(): Promise<BehaviorPrefs> {
  const saved = await chrome.storage.local.get(STORAGE.behaviorForgePrefs)
  const raw = saved[STORAGE.behaviorForgePrefs]
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_BEHAVIOR_PREFS }
  const merged: BehaviorPrefs = { ...DEFAULT_BEHAVIOR_PREFS, ...(raw as Partial<BehaviorPrefs>) }
  if ((merged._v ?? 1) < BEHAVIOR_PREFS_VERSION) {
    merged.captureDom = DEFAULT_BEHAVIOR_PREFS.captureDom
    merged._v = BEHAVIOR_PREFS_VERSION
    await chrome.storage.local.set({ [STORAGE.behaviorForgePrefs]: merged })
  }
  return merged
}

export async function saveBehaviorPrefs(patch: Partial<BehaviorPrefs>): Promise<BehaviorPrefs> {
  const next = { ...(await loadBehaviorPrefs()), ...patch, _v: BEHAVIOR_PREFS_VERSION }
  await chrome.storage.local.set({ [STORAGE.behaviorForgePrefs]: next })
  return next
}
