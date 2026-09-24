import type { eventWithTime } from './types.js'

/** rrweb EventType.FullSnapshot */
const FULL_SNAPSHOT = 2

export function sortRrwebEvents(events: eventWithTime[]): eventWithTime[] {
  return [...events].sort((a, b) => a.timestamp - b.timestamp)
}

export function hasRrwebFullSnapshot(events: eventWithTime[]): boolean {
  return events.some((e) => e.type === FULL_SNAPSHOT)
}

export function rrwebDurationMs(events: eventWithTime[]): number {
  const sorted = sortRrwebEvents(events)
  if (sorted.length < 2) return 0
  return Math.max(0, sorted[sorted.length - 1]!.timestamp - sorted[0]!.timestamp)
}
