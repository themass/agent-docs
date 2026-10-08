import {
  attachNetwork,
  classifyNetworkAttachCauseForTab,
  releaseNetworkDebugger,
  verifyNetworkDebuggerAttached,
  type NetworkAttachCause,
} from './network-recorder'

export type NetworkAttachRecoveryResult = {
  attached: boolean
  tabId: number
  cause: NetworkAttachCause
  error?: string
  /** Human-readable recovery steps already attempted (for trace). */
  actions: string[]
}

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

async function tryAttachOnce(
  tabId: number,
  opts?: { captureBodies?: boolean }
): Promise<{ attached: boolean; error?: string; cause: NetworkAttachCause }> {
  const verified = await verifyNetworkDebuggerAttached(tabId)
  if (verified) return { attached: true, cause: 'ok' }

  const r = await attachNetwork(tabId, opts)
  if (r.attached && (await verifyNetworkDebuggerAttached(tabId))) {
    return { attached: true, cause: 'ok' }
  }
  const cause = await classifyNetworkAttachCauseForTab(tabId, r.error)
  return { attached: false, error: r.error, cause }
}

/**
 * Auto-recover debugger attach: stale release, retry, duplicate tab when DevTools blocks CDP.
 */
export async function attachNetworkWithRecovery(
  tabId: number,
  opts?: { captureBodies?: boolean }
): Promise<NetworkAttachRecoveryResult> {
  const actions: string[] = []
  let activeTabId = tabId

  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) {
      actions.push(`retry_attach_${attempt + 1}`)
      await releaseNetworkDebugger(activeTabId)
      actions.push('released_debugger')
      await sleep(120 * attempt)
    }
    const tryOnce = await tryAttachOnce(activeTabId, opts)
    if (tryOnce.attached) {
      return { attached: true, tabId: activeTabId, cause: 'ok', actions }
    }
    if (tryOnce.cause === 'devtools_open' || tryOnce.cause === 'foreign_debugger') {
      break
    }
  }

  const blocked = await tryAttachOnce(activeTabId, opts)
  if (blocked.cause === 'devtools_open' || blocked.cause === 'foreign_debugger') {
    try {
      const dup = await chrome.tabs.duplicate(activeTabId)
      if (dup?.id != null) {
        actions.push('duplicated_tab_to_escape_debugger')
        activeTabId = dup.id
        await sleep(500)
        const onDup = await tryAttachOnce(activeTabId, opts)
        if (onDup.attached) {
          return { attached: true, tabId: activeTabId, cause: 'ok', actions }
        }
        return {
          attached: false,
          tabId: activeTabId,
          cause: onDup.cause,
          error: onDup.error,
          actions,
        }
      }
    } catch (error) {
      actions.push(`duplicate_tab_failed:${(error as Error).message}`)
    }
  }

  return {
    attached: false,
    tabId: activeTabId,
    cause: blocked.cause,
    error: blocked.error,
    actions,
  }
}

export function formatNetworkDegradedNote(result: NetworkAttachRecoveryResult): string {
  const causeLine =
    result.cause === 'devtools_open'
      ? '检测到 DevTools/检查器占用 debugger'
      : result.cause === 'foreign_debugger'
        ? '检测到其它扩展占用 debugger'
        : 'debugger 附加失败'
  const tried = result.actions.length ? `已自动尝试：${result.actions.join(' → ')}。` : ''
  return (
    `${causeLine}。${tried}已降级为 DOM 模式：仍可提取视频标题与页面链接；` +
    '播放地址（m3u8/mp4）需在 system_done 中写明 shortfall。'
  )
}
