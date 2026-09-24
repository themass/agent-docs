import type { NetworkEvent } from '@naviforge/network-plane'

export type BehaviorNetworkRequest = {
  id: string
  method: string
  url: string
  status?: number
  type?: string
  api?: boolean
  /** ms from session recording start */
  startMs: number
  durationMs: number
}

export type BehaviorNetworkDigest = {
  requestCount: number
  errorCount: number
  xhrCount: number
  statuses: Record<string, number>
  samples: Array<{ method: string; url: string; status?: number }>
  requests: BehaviorNetworkRequest[]
}

const MAX_REQUESTS = 80

function shortApiUrl(url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname.length > 48 ? `${u.pathname.slice(0, 45)}…` : u.pathname
    return `${u.hostname}${path}`
  } catch {
    return url.slice(0, 64)
  }
}

function isApiLike(e: NetworkEvent): boolean {
  return (
    e.type === 'XHR' ||
    e.type === 'Fetch' ||
    /\/api\/|graphql|\.json(\?|$)/i.test(e.url)
  )
}

function toRequest(e: NetworkEvent, sessionStartedAt: number): BehaviorNetworkRequest {
  return {
    id: e.id,
    method: e.method,
    url: shortApiUrl(e.url),
    status: e.status,
    type: e.type,
    api: isApiLike(e),
    startMs: Math.max(0, e.ts - sessionStartedAt),
    durationMs: e.durationMs ?? 0,
  }
}

export function summarizeNetworkEvents(
  events: NetworkEvent[],
  sessionStartedAt = Date.now()
): BehaviorNetworkDigest {
  const statuses: Record<string, number> = {}
  let errorCount = 0
  let xhrCount = 0
  const samples: BehaviorNetworkDigest['samples'] = []
  const requests: BehaviorNetworkRequest[] = []

  for (const e of events) {
    const code = e.status != null ? String(e.status) : 'pending'
    statuses[code] = (statuses[code] ?? 0) + 1
    if (e.status != null && e.status >= 400) errorCount++
    const api = isApiLike(e)
    if (api) {
      xhrCount++
      if (samples.length < 24) {
        samples.push({ method: e.method, url: shortApiUrl(e.url), status: e.status })
      }
    }
    if (e.status == null && e.durationMs == null) continue
    requests.push(toRequest(e, sessionStartedAt))
  }

  requests.sort((a, b) => a.startMs - b.startMs || b.durationMs - a.durationMs)
  const apiFirst = [
    ...requests.filter((r) => r.api),
    ...requests.filter((r) => !r.api),
  ]
  const seen = new Set<string>()
  const capped: BehaviorNetworkRequest[] = []
  for (const r of apiFirst) {
    if (seen.has(r.id)) continue
    seen.add(r.id)
    capped.push(r)
    if (capped.length >= MAX_REQUESTS) break
  }

  return {
    requestCount: events.length,
    errorCount,
    xhrCount,
    statuses,
    samples,
    requests: capped,
  }
}
