import type { ToolResult } from '@naviforge/shared'

export type NetworkEvent = {
  id: string
  method: string
  url: string
  status?: number
  mimeType?: string
  type?: string
  ts: number
  /** Wall-clock ms from request start to loadingFinished/Failed (when known). */
  durationMs?: number
  /** Association hint only — not strict causality. */
  associatedActionId?: string
  /** Truncated response body when capture is enabled (JSON/text only). */
  bodyPreview?: string
  bodyKind?: 'json' | 'text' | 'binary'
}

export type NetworkDigest = {
  count: number
  recent: NetworkEvent[]
  byStatus: Record<string, number>
}

export type NetworkWaitOpts = {
  urlIncludes?: string
  urlRegex?: string
  method?: string
  status?: number
  timeoutMs?: number
}

export type NetworkFilter = {
  urlIncludes?: string
  method?: string
  status?: number
  limit?: number
}

export type NetworkInterceptAction = 'block' | 'mock' | 'forward' | 'rewrite'

export type NetworkInterceptRule = {
  id: string
  /** Substring match on request URL. */
  urlIncludes?: string
  urlRegex?: string
  method?: string
  action: NetworkInterceptAction
  /** mock */
  status?: number
  body?: string
  responseHeaders?: Record<string, string>
  /** forward — absolute URL to continue with */
  forwardUrl?: string
  /** rewrite request headers before continue/forward */
  setHeaders?: Record<string, string>
  removeHeaders?: string[]
}

/**
 * Network observation + interception plane.
 * Chrome implementation uses chrome.debugger (Network + Fetch).
 */
export interface NetworkPlane {
  start(): Promise<ToolResult<{ attached: boolean }>>
  stop(): Promise<ToolResult<{ detached: boolean }>>
  digest(limit?: number): Promise<ToolResult<NetworkDigest>>
  list(filter?: NetworkFilter): Promise<ToolResult<NetworkEvent[]>>
  /** Fetch stored body preview for a captured request id. */
  getBody?(id: string): Promise<ToolResult<{ body: string; kind: 'json' | 'text' | 'binary' }>>
  wait(opts: NetworkWaitOpts): Promise<ToolResult<NetworkEvent>>
  clear(): Promise<ToolResult<{ cleared: true }>>
  /** Install/replace intercept rules and enable Fetch interception. */
  setIntercepts?(
    rules: NetworkInterceptRule[]
  ): Promise<ToolResult<{ enabled: boolean; count: number }>>
  listIntercepts?(): Promise<ToolResult<NetworkInterceptRule[]>>
  clearIntercepts?(): Promise<ToolResult<{ cleared: true }>>
  /** B2: captured external script bodies (when captureBodies enabled). */
  listScriptBodies?(opts?: { limit?: number }): Promise<ToolResult<Array<{ url: string; preview: string }>>>
  /** F2: CDP Page.getResourceContent for script URLs not yet captured. */
  fetchScriptContents?(
    urls: string[]
  ): Promise<ToolResult<Array<{ url: string; preview: string }>>>
}

export function formatDigest(d: NetworkDigest): string {
  if (!d.count) return 'NETWORK: (empty)'
  const lines = d.recent.map(
    (e) => `${e.method} ${e.status ?? '-'} ${truncateUrl(e.url)} [${e.type ?? ''}]`
  )
  return `NETWORK digest count=${d.count}\n${lines.join('\n')}`
}

function truncateUrl(url: string, max = 120): string {
  return url.length <= max ? url : url.slice(0, max) + '…'
}

/** Match wait opts against an event (pure, testable). */
export function matchNetworkEvent(e: NetworkEvent, opts: NetworkWaitOpts): boolean {
  if (opts.method && e.method.toUpperCase() !== opts.method.toUpperCase()) return false
  if (opts.status != null && e.status !== opts.status) return false
  if (opts.urlIncludes && !e.url.includes(opts.urlIncludes)) return false
  if (opts.urlRegex) {
    try {
      if (!new RegExp(opts.urlRegex).test(e.url)) return false
    } catch {
      return false
    }
  }
  return true
}

export function matchInterceptRule(
  request: { url: string; method: string },
  rule: NetworkInterceptRule
): boolean {
  if (rule.method && request.method.toUpperCase() !== rule.method.toUpperCase()) return false
  if (rule.urlIncludes && !request.url.includes(rule.urlIncludes)) return false
  if (rule.urlRegex) {
    try {
      if (!new RegExp(rule.urlRegex).test(request.url)) return false
    } catch {
      return false
    }
  }
  return Boolean(rule.urlIncludes || rule.urlRegex || rule.method)
}

export function buildDigest(events: NetworkEvent[], limit = 12): NetworkDigest {
  const recent = events.slice(-limit)
  const byStatus: Record<string, number> = {}
  for (const e of events) {
    const k = e.status != null ? String(e.status) : 'pending'
    byStatus[k] = (byStatus[k] ?? 0) + 1
  }
  return { count: events.length, recent, byStatus }
}
