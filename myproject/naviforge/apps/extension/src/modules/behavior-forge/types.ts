import type { BehaviorNetworkDigest } from './network-summary.js'

/** Relative ms from session start. */
export type BehaviorEvent =
  | { t: number; kind: 'viewport'; w: number; h: number; dpr: number }
  | { t: number; kind: 'pointer'; x: number; y: number }
  | { t: number; kind: 'click'; x: number; y: number; button: number; tag?: string }
  | { t: number; kind: 'scroll'; scrollX: number; scrollY: number }
  | { t: number; kind: 'nav'; url: string; title?: string }
  | { t: number; kind: 'idle'; durationMs: number }
  | { t: number; kind: 'key'; key: string; meta?: boolean }

export type BehaviorSessionMeta = {
  id: string
  startedAt: string
  endedAt?: string
  title: string
  originUrl: string
  eventCount: number
  durationMs: number
  viewport?: { w: number; h: number }
  /** True when rrweb DOM events were captured. */
  hasRrweb?: boolean
  rrwebEventCount?: number
  /** Synced to NewAPI cloud. */
  cloudId?: string
  /** Network plane digest captured during recording (debugger). */
  networkDigest?: BehaviorNetworkDigest
}

export type BehaviorSessionRecord = BehaviorSessionMeta & {
  events: BehaviorEvent[]
  /** Loaded on demand — stored in a separate chrome.storage key when large. */
  rrwebEvents?: eventWithTime[]
}

/** rrweb serialized event (re-export for callers). */
export type { eventWithTime } from 'rrweb'

export type BehaviorPrefs = {
  /** Pointer sample interval cap (ms). */
  pointerThrottleMs: number
  idleThresholdMs: number
  /** rrweb DOM capture — on by default for usable replay. */
  captureDom: boolean
  /** Bumped when default prefs change (migration). */
  _v?: number
}

export const BEHAVIOR_PREFS_VERSION = 2

export const DEFAULT_BEHAVIOR_PREFS: BehaviorPrefs = {
  pointerThrottleMs: 80,
  idleThresholdMs: 5000,
  captureDom: true,
  _v: BEHAVIOR_PREFS_VERSION,
}
