import type {
  NetworkDigest,
  NetworkEvent,
  NetworkFilter,
  NetworkInterceptRule,
  NetworkPlane,
  NetworkWaitOpts,
} from '@naviforge/network-plane'
import type { ToolResult } from '@naviforge/shared'

type Msg =
  | { type: 'NETWORK'; action: 'attach'; tabId: number; captureBodies?: boolean }
  | { type: 'NETWORK'; action: 'detach'; tabId: number }
  | { type: 'NETWORK'; action: 'digest'; tabId: number; limit?: number }
  | { type: 'NETWORK'; action: 'list'; tabId: number; filter?: NetworkFilter }
  | { type: 'NETWORK'; action: 'wait'; tabId: number; opts: NetworkWaitOpts }
  | { type: 'NETWORK'; action: 'cancelWaits'; tabId: number }
  | { type: 'NETWORK'; action: 'clear'; tabId: number }
  | { type: 'NETWORK'; action: 'setIntercepts'; tabId: number; rules: NetworkInterceptRule[] }
  | { type: 'NETWORK'; action: 'listIntercepts'; tabId: number }
  | { type: 'NETWORK'; action: 'clearIntercepts'; tabId: number }
  | { type: 'NETWORK'; action: 'getBody'; tabId: number; id: string }
  | { type: 'NETWORK'; action: 'fetch_script_bodies'; tabId: number; urls: string[] }
  | { type: 'NETWORK'; action: 'release_run'; tabId: number }
  | { type: 'NETWORK'; action: 'script_bodies'; tabId: number; limit?: number }

function send<T>(msg: Msg): Promise<T | undefined> {
  return import('./extension-runtime.js').then(({ safeRuntimeSendMessage }) =>
    safeRuntimeSendMessage<T>(msg)
  )
}

export function createChromeNetworkPlane(
  getTabId: () => number,
  opts?: { captureBodies?: boolean; getSignal?: () => AbortSignal | undefined }
): NetworkPlane {
  const captureBodies = opts?.captureBodies === true
  const getSignal = opts?.getSignal

  async function attachTab(): Promise<ToolResult<{ attached: boolean }>> {
    const tabId = getTabId()
    const digestProbe = await send<{ ok: boolean; data?: NetworkDigest; error?: string }>({
      type: 'NETWORK',
      action: 'digest',
      tabId,
      limit: 1,
    })
    if (digestProbe?.ok && digestProbe.data) {
      return { ok: true, data: { attached: true } }
    }
    const r = await send<{ ok: boolean; attached?: boolean; error?: string }>({
      type: 'NETWORK',
      action: 'attach',
      tabId,
      captureBodies,
    })
    if (!r?.ok) {
      return {
        ok: false,
        error: {
          code: 'attach_failed',
          message: r?.error ?? 'debugger attach failed',
          recoverable: true,
        },
      }
    }
    return { ok: true, data: { attached: true } }
  }

  return {
    start: attachTab,
    async stop(): Promise<ToolResult<{ detached: boolean }>> {
      await send({ type: 'NETWORK', action: 'release_run', tabId: getTabId() })
      return { ok: true, data: { detached: true } }
    },
    async digest(limit = 12): Promise<ToolResult<NetworkDigest>> {
      let r = await send<{ ok: boolean; data?: NetworkDigest; error?: string }>({
        type: 'NETWORK',
        action: 'digest',
        tabId: getTabId(),
        limit,
      })
      if (!r?.ok || !r.data) {
        const reattached = await attachTab()
        if (reattached.ok) {
          r = await send<{ ok: boolean; data?: NetworkDigest; error?: string }>({
            type: 'NETWORK',
            action: 'digest',
            tabId: getTabId(),
            limit,
          })
        }
      }
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: { code: 'digest_failed', message: r?.error ?? 'digest failed', recoverable: true },
        }
      }
      return { ok: true, data: r.data }
    },
    async list(filter?: NetworkFilter): Promise<ToolResult<NetworkEvent[]>> {
      let r = await send<{ ok: boolean; data?: NetworkEvent[]; error?: string }>({
        type: 'NETWORK',
        action: 'list',
        tabId: getTabId(),
        filter,
      })
      if (!r?.ok || !r.data) {
        const reattached = await attachTab()
        if (reattached.ok) {
          r = await send<{ ok: boolean; data?: NetworkEvent[]; error?: string }>({
            type: 'NETWORK',
            action: 'list',
            tabId: getTabId(),
            filter,
          })
        }
      }
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: { code: 'list_failed', message: r?.error ?? 'list failed', recoverable: true },
        }
      }
      return { ok: true, data: r.data }
    },
    async getBody(id: string) {
      const r = await send<{
        ok: boolean
        data?: { body: string; kind: 'json' | 'text' | 'binary' }
        error?: string
      }>({
        type: 'NETWORK',
        action: 'getBody',
        tabId: getTabId(),
        id,
      })
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: {
            code: 'body_missing',
            message: r?.error ?? 'response body not captured',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: r.data }
    },
    async wait(opts: NetworkWaitOpts): Promise<ToolResult<NetworkEvent>> {
      const signal = getSignal?.()
      const onAbort = () => {
        void send({ type: 'NETWORK', action: 'cancelWaits', tabId: getTabId() })
      }
      signal?.addEventListener('abort', onAbort, { once: true })
      try {
        const r = await send<{ ok: boolean; data?: NetworkEvent; error?: string }>({
          type: 'NETWORK',
          action: 'wait',
          tabId: getTabId(),
          opts,
        })
        if (!r?.ok || !r.data) {
          const cancelled = r?.error === 'cancelled' || signal?.aborted
          return {
            ok: false,
            error: {
              code: cancelled ? 'cancelled' : 'wait_timeout',
              message: cancelled
                ? 'network wait cancelled'
                : (r?.error ?? 'network wait timeout'),
              recoverable: true,
            },
          }
        }
        return { ok: true, data: r.data }
      } finally {
        signal?.removeEventListener('abort', onAbort)
      }
    },
    async clear(): Promise<ToolResult<{ cleared: true }>> {
      await send({ type: 'NETWORK', action: 'clear', tabId: getTabId() })
      return { ok: true, data: { cleared: true } }
    },
    async setIntercepts(rules) {
      const r = await send<{
        ok: boolean
        enabled?: boolean
        count?: number
        error?: string
      }>({
        type: 'NETWORK',
        action: 'setIntercepts',
        tabId: getTabId(),
        rules,
      })
      if (!r?.ok) {
        return {
          ok: false,
          error: {
            code: 'intercept_failed',
            message: r?.error ?? 'intercept failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { enabled: Boolean(r.enabled), count: r.count ?? 0 } }
    },
    async listIntercepts() {
      const r = await send<{ ok: boolean; data?: NetworkInterceptRule[]; error?: string }>({
        type: 'NETWORK',
        action: 'listIntercepts',
        tabId: getTabId(),
      })
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: {
            code: 'list_intercepts_failed',
            message: r?.error ?? 'list intercepts failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: r.data }
    },
    async clearIntercepts() {
      const r = await send<{ ok: boolean; error?: string }>({
        type: 'NETWORK',
        action: 'clearIntercepts',
        tabId: getTabId(),
      })
      if (!r?.ok) {
        return {
          ok: false,
          error: {
            code: 'clear_intercepts_failed',
            message: r?.error ?? 'clear intercepts failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: { cleared: true } }
    },
    async listScriptBodies(opts?: { limit?: number }) {
      const r = await send<{ ok: boolean; data?: Array<{ url: string; preview: string }>; error?: string }>({
        type: 'NETWORK',
        action: 'script_bodies',
        tabId: getTabId(),
        limit: opts?.limit ?? 6,
      })
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: {
            code: 'script_bodies_failed',
            message: r?.error ?? 'script bodies failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: r.data }
    },
    async fetchScriptContents(urls: string[]) {
      const r = await send<{ ok: boolean; data?: Array<{ url: string; preview: string }>; error?: string }>({
        type: 'NETWORK',
        action: 'fetch_script_bodies',
        tabId: getTabId(),
        urls,
      })
      if (!r?.ok || !r.data) {
        return {
          ok: false,
          error: {
            code: 'fetch_script_failed',
            message: r?.error ?? 'fetch script failed',
            recoverable: true,
          },
        }
      }
      return { ok: true, data: r.data }
    },
  }
}
