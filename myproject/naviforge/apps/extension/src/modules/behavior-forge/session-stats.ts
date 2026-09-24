import type { BehaviorEvent, BehaviorSessionRecord } from './types.js'

export type SessionStats = {
  clicks: number
  scrolls: number
  pages: number
  keys: number
  idleMs: number
  activeMs: number
  pointerSamples: number
}

export function computeSessionStats(events: BehaviorEvent[], durationMs: number): SessionStats {
  let clicks = 0
  let scrolls = 0
  let pages = 0
  let keys = 0
  let idleMs = 0
  let pointerSamples = 0
  for (const e of events) {
    if (e.kind === 'click') clicks++
    else if (e.kind === 'scroll') scrolls++
    else if (e.kind === 'nav') pages++
    else if (e.kind === 'key') keys++
    else if (e.kind === 'idle') idleMs += e.durationMs
    else if (e.kind === 'pointer') pointerSamples++
  }
  const activeMs = Math.max(0, durationMs - idleMs)
  return { clicks, scrolls, pages: Math.max(1, pages), keys, idleMs, activeMs, pointerSamples }
}

export function formatDurationSec(ms: number): string {
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  return `${m}m ${s % 60}s`
}

export function pageDwellLines(events: BehaviorEvent[]): Array<{ url: string; ms: number }> {
  const navs = events.filter((e): e is Extract<BehaviorEvent, { kind: 'nav' }> => e.kind === 'nav')
  if (!navs.length) return []
  const lines: Array<{ url: string; ms: number }> = []
  for (let i = 0; i < navs.length; i++) {
    const start = navs[i]!.t
    const end = navs[i + 1]?.t ?? events[events.length - 1]?.t ?? start
    lines.push({ url: navs[i]!.url, ms: Math.max(0, end - start) })
  }
  return lines.slice(-8)
}

export function statsForSession(session: BehaviorSessionRecord): SessionStats {
  return computeSessionStats(session.events, session.durationMs)
}
