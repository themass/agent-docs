import {
  buildDigest,
  matchInterceptRule,
  matchNetworkEvent,
  type NetworkEvent,
  type NetworkFilter,
  type NetworkInterceptRule,
  type NetworkWaitOpts,
} from '@naviforge/network-plane'

type TabBucket = {
  events: NetworkEvent[]
  pending: Map<string, Partial<NetworkEvent>>
  intercepts: NetworkInterceptRule[]
  fetchEnabled: boolean
  captureBodies: boolean
  bodies: Map<string, { body: string; kind: 'json' | 'text' | 'binary' }>
  /** Current main-frame URL for this slice. */
  pageUrl?: string
  /** Prior navigation slices (newest last). */
  segments: Array<{ url: string; events: NetworkEvent[]; at: number }>
}

const byTab = new Map<number, TabBucket>()
const attachedTabs = new Set<number>()
const waitAbortByTab = new Map<number, AbortController>()
const MAX = 200
const MAX_BODY_CHARS = 32_768

function bucket(tabId: number): TabBucket {
  let b = byTab.get(tabId)
  if (!b) {
    b = {
      events: [],
      pending: new Map(),
      intercepts: [],
      fetchEnabled: false,
      captureBodies: false,
      bodies: new Map(),
      segments: [],
    }
    byTab.set(tabId, b)
  } else if (!b.segments) {
    // ponytail: hot-reload may leave pre-B buckets without segments
    b.segments = []
  }
  return b
}

function redactBody(text: string): string {
  return text
    .replace(/(authorization"\s*:\s*")[^"]+"/gi, '$1[REDACTED]"')
    .replace(/(Bearer\s+)[^\s"']+/gi, '$1[REDACTED]')
    .slice(0, MAX_BODY_CHARS)
}

function bodyKindFor(mimeType: string | undefined, url: string): 'json' | 'text' | 'binary' {
  if (/json/i.test(mimeType ?? '') || /\/json/i.test(url)) return 'json'
  if (/text|xml|javascript|mpegurl/i.test(mimeType ?? '')) return 'text'
  return 'binary'
}

export function configureNetworkTab(
  tabId: number,
  opts: { captureBodies?: boolean }
): void {
  bucket(tabId).captureBodies = opts.captureBodies === true
}

export function getNetworkBody(
  tabId: number,
  id: string
): { body: string; kind: 'json' | 'text' | 'binary' } | null {
  return bucket(tabId).bodies.get(id) ?? null
}

function pushEvent(tabId: number, e: NetworkEvent) {
  const b = bucket(tabId)
  b.events.push(e)
  if (b.events.length > MAX) b.events.splice(0, b.events.length - MAX)
}

export function clearNetwork(tabId?: number) {
  if (tabId == null) {
    byTab.clear()
    return
  }
  const keep = byTab.get(tabId)
  byTab.delete(tabId)
  if (keep) {
    byTab.set(tabId, {
      events: [],
      pending: new Map(),
      intercepts: keep.intercepts,
      fetchEnabled: keep.fetchEnabled,
      captureBodies: keep.captureBodies,
      bodies: new Map(),
      pageUrl: undefined,
      segments: [],
    })
  }
}

export function listNetwork(tabId: number, filter?: NetworkFilter): NetworkEvent[] {
  const events = bucket(tabId).events
  let out = events
  if (filter?.method) out = out.filter((e) => e.method === filter.method!.toUpperCase())
  if (filter?.status != null) out = out.filter((e) => e.status === filter.status)
  if (filter?.urlIncludes) out = out.filter((e) => e.url.includes(filter.urlIncludes!))
  const limit = filter?.limit ?? 50
  return out.slice(-limit)
}

export function digestNetwork(tabId: number, limit = 12) {
  return buildDigest(bucket(tabId).events, limit)
}

/** C: start a new network slice when the tab navigates. */
export function segmentNetworkTab(tabId: number, url: string): void {
  const b = bucket(tabId)
  if (b.events.length && b.pageUrl) {
    b.segments.push({ url: b.pageUrl, events: [...b.events], at: Date.now() })
    if (b.segments.length > 8) b.segments.splice(0, b.segments.length - 8)
  }
  b.events = []
  b.pending.clear()
  b.pageUrl = url
}

/** B2: script response previews captured while captureBodies is on. */
export function listScriptBodyPreviews(
  tabId: number,
  limit = 6
): Array<{ url: string; preview: string }> {
  const b = bucket(tabId)
  const out: Array<{ url: string; preview: string }> = []
  for (const ev of [...b.events].reverse()) {
    if (!/javascript|\.js(?:\?|$)/i.test(ev.url)) continue
    const stored = b.bodies.get(ev.id)
    if (!stored || stored.kind === 'binary') continue
    out.push({ url: ev.url, preview: stored.body.slice(0, 12_000) })
    if (out.length >= limit) break
  }
  for (const seg of [...b.segments].reverse()) {
    for (const ev of [...seg.events].reverse()) {
      if (!/javascript|\.js(?:\?|$)/i.test(ev.url)) continue
      const stored = b.bodies.get(ev.id)
      if (!stored || stored.kind === 'binary') continue
      if (out.some((item) => item.url === ev.url)) continue
      out.push({ url: ev.url, preview: stored.body.slice(0, 12_000) })
      if (out.length >= limit) break
    }
    if (out.length >= limit) break
  }
  return out
}

/** F2: proactively pull script text via CDP when debugger is attached. */
export async function fetchMissingScriptBodies(
  tabId: number,
  urls: string[],
  limit = 4
): Promise<Array<{ url: string; preview: string }>> {
  if (!attachedTabs.has(tabId) || !urls.length) return []
  const known = new Set(listScriptBodyPreviews(tabId, 24).map((item) => item.url))
  const out: Array<{ url: string; preview: string }> = []
  for (const url of urls) {
    if (known.has(url) || out.some((item) => item.url === url)) continue
    if (!/javascript|\.js(?:\?|$)/i.test(url)) continue
    try {
      const result = (await chrome.debugger.sendCommand({ tabId }, 'Page.getResourceContent', {
        url,
      })) as { content?: string; base64Encoded?: boolean }
      let text = result.content ?? ''
      if (result.base64Encoded && text) {
        try {
          text = atob(text)
        } catch {
          continue
        }
      }
      if (!text.trim()) continue
      out.push({ url, preview: text.slice(0, 12_000) })
      if (out.length >= limit) break
    } catch {
      /* cross-origin or resource not in tree */
    }
  }
  return out
}

export function cancelNetworkWaits(tabId: number): void {
  waitAbortByTab.get(tabId)?.abort()
  waitAbortByTab.delete(tabId)
}

function sleepMs(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve()
  if (signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  return new Promise((resolve, reject) => {
    const id = setTimeout(resolve, ms)
    const onAbort = () => {
      clearTimeout(id)
      reject(new DOMException('Aborted', 'AbortError'))
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export async function waitNetwork(
  tabId: number,
  opts: NetworkWaitOpts,
  signal?: AbortSignal
): Promise<NetworkEvent | null> {
  const local = new AbortController()
  waitAbortByTab.set(tabId, local)
  const onExternalAbort = () => local.abort()
  signal?.addEventListener('abort', onExternalAbort, { once: true })

  try {
    const timeout = opts.timeoutMs ?? 10000
    const start = Date.now()
    const seen = new Set(bucket(tabId).events.map((e) => e.id))
    const combined = () => local.signal.aborted || signal?.aborted

    while (Date.now() - start < timeout) {
      if (combined()) throw new DOMException('Network wait cancelled', 'AbortError')
      for (const e of bucket(tabId).events) {
        if (seen.has(e.id)) continue
        seen.add(e.id)
        if (matchNetworkEvent(e, opts)) return e
      }
      for (const e of bucket(tabId).events) {
        if (matchNetworkEvent(e, opts) && !seen.has(`matched:${e.id}`)) {
          return e
        }
      }
      try {
        await sleepMs(200, local.signal)
      } catch (error) {
        if ((error as Error).name === 'AbortError') {
          throw new DOMException('Network wait cancelled', 'AbortError')
        }
        throw error
      }
    }
    for (const e of [...bucket(tabId).events].reverse()) {
      if (matchNetworkEvent(e, opts)) return e
    }
    return null
  } finally {
    signal?.removeEventListener('abort', onExternalAbort)
    if (waitAbortByTab.get(tabId) === local) waitAbortByTab.delete(tabId)
  }
}

export async function attachNetwork(
  tabId: number,
  opts?: { captureBodies?: boolean }
): Promise<{ attached: boolean; error?: string }> {
  if (opts?.captureBodies != null) configureNetworkTab(tabId, { captureBodies: opts.captureBodies })
  if (attachedTabs.has(tabId)) {
    const targets = await chrome.debugger.getTargets()
    const target = targets.find((item) => item.tabId === tabId)
    const ours =
      target?.attached &&
      (!target.extensionId || target.extensionId === chrome.runtime.id)
    if (ours) return { attached: true }
    attachedTabs.delete(tabId)
  }
  try {
    await chrome.debugger.attach({ tabId }, '1.3')
  } catch (e) {
    const msg = (e as Error).message ?? String(e)
    if (!/already attached/i.test(msg)) {
      return { attached: false, error: msg }
    }
  }
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Network.enable', {
      maxResourceBufferSize: 0,
      maxPostDataSize: 0,
    })
    // ponytail: keep session events across re-attach; clear only via explicit clearNetwork / navigation.
    const b = bucket(tabId)
    if (b.intercepts.length) {
      await enableFetch(tabId)
    }
    attachedTabs.add(tabId)
    return { attached: true }
  } catch (e) {
    const msg = (e as Error).message ?? String(e)
    if (/already/i.test(msg)) {
      attachedTabs.add(tabId)
      return { attached: true }
    }
    return { attached: false, error: msg }
  }
}

export async function detachNetwork(tabId: number): Promise<{ detached: boolean }> {
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.disable').catch(() => {})
    await chrome.debugger.sendCommand({ tabId }, 'Network.disable').catch(() => {})
    await chrome.debugger.detach({ tabId })
  } catch {
    /* ignore */
  }
  attachedTabs.delete(tabId)
  byTab.delete(tabId)
  return { detached: true }
}

/** Soft detach at run end — keep bucket when toolkit session is bound. */
export async function releaseNetworkDebugger(tabId: number): Promise<void> {
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.disable').catch(() => {})
    await chrome.debugger.sendCommand({ tabId }, 'Network.disable').catch(() => {})
    await chrome.debugger.detach({ tabId })
  } catch {
    /* ignore */
  }
  attachedTabs.delete(tabId)
}

async function enableFetch(tabId: number): Promise<void> {
  await chrome.debugger.sendCommand({ tabId }, 'Fetch.enable', {
    patterns: [{ urlPattern: '*', requestStage: 'Request' }],
  })
  bucket(tabId).fetchEnabled = true
}

export function listIntercepts(tabId: number): NetworkInterceptRule[] {
  return [...bucket(tabId).intercepts]
}

export async function setIntercepts(
  tabId: number,
  rules: NetworkInterceptRule[]
): Promise<{ enabled: boolean; count: number; error?: string }> {
  const b = bucket(tabId)
  b.intercepts = rules.slice(0, 50).map((rule) => ({
    ...rule,
    id: rule.id || crypto.randomUUID(),
    body: rule.body?.slice(0, 200_000),
  }))
  try {
    const attached = await attachNetwork(tabId)
    if (!attached.attached) return { enabled: false, count: 0, error: attached.error }
    if (b.intercepts.length) await enableFetch(tabId)
    else {
      await chrome.debugger.sendCommand({ tabId }, 'Fetch.disable').catch(() => {})
      b.fetchEnabled = false
    }
    return { enabled: b.fetchEnabled, count: b.intercepts.length }
  } catch (e) {
    return { enabled: false, count: 0, error: (e as Error).message }
  }
}

export async function clearIntercepts(tabId: number): Promise<{ cleared: true }> {
  bucket(tabId).intercepts = []
  try {
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.disable').catch(() => {})
  } catch {
    /* ignore */
  }
  bucket(tabId).fetchEnabled = false
  return { cleared: true }
}

function headersArray(headers?: Record<string, string>): Array<{ name: string; value: string }> {
  if (!headers) return []
  return Object.entries(headers).map(([name, value]) => ({ name, value: String(value) }))
}

async function handleFetchPaused(tabId: number, params: Record<string, unknown>): Promise<void> {
  const requestId = String(params.requestId)
  const request = (params.request ?? {}) as {
    url?: string
    method?: string
    headers?: Record<string, string>
  }
  const url = request.url ?? ''
  const method = (request.method ?? 'GET').toUpperCase()
  const rule = bucket(tabId).intercepts.find((item) => matchInterceptRule({ url, method }, item))

  if (!rule) {
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.continueRequest', { requestId })
    return
  }

  if (rule.action === 'block') {
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.failRequest', {
      requestId,
      errorReason: 'BlockedByClient',
    })
    pushEvent(tabId, {
      id: `block-${requestId}`,
      method,
      url,
      status: 0,
      type: 'intercept-block',
      ts: Date.now(),
    })
    return
  }

  if (rule.action === 'mock') {
    const body = rule.body ?? ''
    await chrome.debugger.sendCommand({ tabId }, 'Fetch.fulfillRequest', {
      requestId,
      responseCode: rule.status ?? 200,
      responseHeaders: headersArray(rule.responseHeaders).length
        ? headersArray(rule.responseHeaders)
        : [{ name: 'Content-Type', value: 'application/json' }],
      body: btoa(unescape(encodeURIComponent(body))),
    })
    pushEvent(tabId, {
      id: `mock-${requestId}`,
      method,
      url,
      status: rule.status ?? 200,
      type: 'intercept-mock',
      ts: Date.now(),
    })
    return
  }

  const headers = { ...(request.headers ?? {}) }
  for (const name of rule.removeHeaders ?? []) delete headers[name]
  Object.assign(headers, rule.setHeaders ?? {})
  const continueParams: Record<string, unknown> = { requestId }
  if (rule.setHeaders || rule.removeHeaders?.length) {
    continueParams.headers = headersArray(headers)
  }
  if (rule.action === 'forward' && rule.forwardUrl) continueParams.url = rule.forwardUrl
  await chrome.debugger.sendCommand({ tabId }, 'Fetch.continueRequest', continueParams)
  pushEvent(tabId, {
    id: `rewrite-${requestId}`,
    method,
    url: String(continueParams.url ?? url),
    type: rule.action === 'forward' ? 'intercept-forward' : 'intercept-rewrite',
    ts: Date.now(),
  })
}

let listening = false

export function ensureNetworkListeners() {
  if (listening) return
  listening = true

  chrome.debugger.onEvent.addListener((source, method, params) => {
    const tabId = source.tabId
    if (tabId == null || !params) return
    const b = bucket(tabId)
    const p = params as Record<string, unknown>

    if (method === 'Fetch.requestPaused') {
      void handleFetchPaused(tabId, p).catch((error) => {
        console.error('Fetch intercept failed', error)
        void chrome.debugger
          .sendCommand({ tabId }, 'Fetch.continueRequest', { requestId: String(p.requestId) })
          .catch(() => {})
      })
      return
    }

    if (method === 'Network.requestWillBeSent') {
      const requestId = String(p.requestId)
      const request = p.request as { method?: string; url?: string }
      b.pending.set(requestId, {
        id: requestId,
        method: (request.method ?? 'GET').toUpperCase(),
        url: request.url ?? '',
        ts: Date.now(),
        type: String(p.type ?? ''),
      })
    }

    if (method === 'Network.responseReceived') {
      const requestId = String(p.requestId)
      const response = p.response as { status?: number; mimeType?: string; url?: string }
      const pending = b.pending.get(requestId) ?? {
        id: requestId,
        method: 'GET',
        url: response.url ?? '',
        ts: Date.now(),
      }
      pending.status = response.status
      pending.mimeType = response.mimeType
      pending.url = response.url ?? pending.url
      b.pending.set(requestId, pending)
    }

    if (method === 'Network.loadingFinished' || method === 'Network.loadingFailed') {
      const requestId = String(p.requestId)
      const pending = b.pending.get(requestId)
      if (!pending?.url) return
      b.pending.delete(requestId)
      const started = pending.ts ?? Date.now()
      const finished = Date.now()
      const event: NetworkEvent = {
        id: requestId,
        method: pending.method ?? 'GET',
        url: pending.url,
        status: pending.status,
        mimeType: pending.mimeType,
        type: pending.type,
        ts: started,
        durationMs: Math.max(0, finished - started),
      }

      if (b.captureBodies && method === 'Network.loadingFinished') {
        const encoded = Number(p.encodedDataLength ?? 0)
        const mime = pending.mimeType ?? ''
        const kind = bodyKindFor(mime, pending.url)
        if (encoded > 0 && encoded <= MAX_BODY_CHARS && kind !== 'binary') {
          void chrome.debugger
            .sendCommand({ tabId }, 'Network.getResponseBody', { requestId })
            .then((raw) => {
              const body = raw as { body?: string; base64Encoded?: boolean }
              if (!body.body) return
              const text = body.base64Encoded
                ? atob(body.body.replace(/\s/g, ''))
                : body.body
              const preview = redactBody(text)
              b.bodies.set(requestId, { body: preview, kind })
              const stored = b.events.find((item) => item.id === requestId)
              if (stored) {
                stored.bodyPreview = preview.slice(0, 240)
                stored.bodyKind = kind
              }
            })
            .catch(() => {})
        }
      }

      pushEvent(tabId, event)
    }
  })

  chrome.debugger.onDetach.addListener((source) => {
    if (source.tabId == null) return
    attachedTabs.delete(source.tabId)
  })
}
