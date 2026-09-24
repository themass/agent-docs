import type { BehaviorEvent, BehaviorSessionRecord } from './types.js'

/** Fix per-page t=0 resets after full navigation (content script reload). */
export function normalizeSessionEvents(events: BehaviorEvent[]): BehaviorEvent[] {
  if (events.length < 2) return events
  const out: BehaviorEvent[] = []
  let offset = 0
  let segmentMax = 0
  for (const e of events) {
    if (e.kind === 'nav' && e.t + offset < segmentMax - 800) {
      offset += segmentMax - e.t + 50
    }
    const t = e.t + offset
    segmentMax = Math.max(segmentMax, t)
    out.push({ ...e, t })
  }
  return out
}

export function replayDurationMs(session: BehaviorSessionRecord): number {
  const events = normalizeSessionEvents(session.events)
  let maxT = 0
  for (const e of events) if (e.t > maxT) maxT = e.t
  return Math.max(session.durationMs, maxT, 1)
}

export function withNormalizedEvents(session: BehaviorSessionRecord): BehaviorSessionRecord {
  const events = normalizeSessionEvents(session.events)
  return { ...session, events, durationMs: replayDurationMs({ ...session, events }) }
}
