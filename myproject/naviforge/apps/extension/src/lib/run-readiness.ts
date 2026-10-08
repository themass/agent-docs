/** Pre-run checks surfaced in Side Panel before agent loop starts. */

import { hasBroadHostAccess } from './host-permissions'

export type RunReadinessItem = {
  id: string
  ok: boolean
  label: string
  detail?: string
  /** When true, Run should not start until fixed. */
  blocking?: boolean
}

function isRestrictedUrl(url: string | undefined): boolean {
  if (!url) return true
  return (
    url.startsWith('chrome://') ||
    url.startsWith('chrome-extension://') ||
    url.startsWith('devtools://') ||
    url.startsWith('edge://') ||
    url.startsWith('about:')
  )
}

async function pingContent(tabId: number): Promise<boolean> {
  try {
    const res = await chrome.runtime.sendMessage({
      type: 'PAGE_CONTROL',
      action: 'ping',
      targetTabId: tabId,
    })
    return !!(res as { ok?: boolean } | undefined)?.ok
  } catch {
    return false
  }
}

async function probeDebugger(tabId: number): Promise<{ ok: boolean; detail?: string }> {
  try {
    const res = await chrome.runtime.sendMessage({
      type: 'NETWORK',
      action: 'probe',
      tabId,
    })
    const payload = res as { ok?: boolean; error?: string }
    return payload?.ok ? { ok: true } : { ok: false, detail: payload?.error ?? 'debugger attach failed' }
  } catch (error) {
    return { ok: false, detail: (error as Error).message }
  }
}

export async function runReadinessChecks(opts: {
  tabId: number
  tabUrl?: string
  tabTitle?: string
  apiKey: string
  useNetwork: boolean
  skillLabel?: string
  enforceSkillAllowlist?: boolean
}): Promise<RunReadinessItem[]> {
  const items: RunReadinessItem[] = []

  items.push({
    id: 'api_key',
    ok: Boolean(opts.apiKey.trim()),
    label: '模型 API Key',
    detail: opts.apiKey.trim() ? '已配置' : '请在 Settings → Models 填写 API Key',
    blocking: true,
  })

  const restricted = isRestrictedUrl(opts.tabUrl)
  items.push({
    id: 'tab_url',
    ok: !restricted,
    label: '目标标签 URL',
    detail: restricted
      ? `无法操作 ${opts.tabUrl ?? '空白页'} — 请打开 http(s) 页面`
      : opts.tabUrl ?? '(unknown)',
    blocking: true,
  })

  const hostAccess = await hasBroadHostAccess()
  items.push({
    id: 'host_access',
    ok: hostAccess,
    label: '网站访问权限',
    detail: hostAccess ? '已授权 http(s)' : '首次 Run 时将请求访问网站',
    blocking: false,
  })

  items.push({
    id: 'content_script',
    ok: false,
    label: 'Content script',
    detail: '检测中…',
    blocking: true,
  })

  if (opts.useNetwork) {
    items.push({
      id: 'debugger',
      ok: false,
      label: 'Network (debugger)',
      detail: '检测中…',
      blocking: false,
    })
  }

  if (opts.skillLabel) {
    items.push({
      id: 'skill',
      ok: true,
      label: 'Skill 路由',
      detail: `${opts.skillLabel}${opts.enforceSkillAllowlist ? ' · 硬白名单已开启' : ' · 仅提示（不拦工具）'}`,
      blocking: false,
    })
  }

  if (!restricted) {
    const alive = await pingContent(opts.tabId)
    const content = items.find((item) => item.id === 'content_script')
    if (content) {
      content.ok = alive
      content.detail = alive
        ? '已连接 — 若刚更新扩展请仍建议刷新页面'
        : '未连接 — 将尝试注入；失败请刷新目标页'
    }
    if (!alive) {
      await new Promise((resolve) => setTimeout(resolve, 120))
      const retry = await pingContent(opts.tabId)
      if (retry && content) {
        content.ok = true
        content.detail = '注入成功（建议刷新页面以稳定索引）'
      }
    }
  }

  if (opts.useNetwork && !restricted) {
    const dbg = await probeDebugger(opts.tabId)
    const item = items.find((i) => i.id === 'debugger')
    if (item) {
      item.ok = dbg.ok
      item.blocking = false
      item.detail = dbg.ok
        ? 'debugger 可附加'
        : `${dbg.detail ?? 'attach failed'} — Run 时将自动重试；仍失败则降级为 DOM 模式（不拦 Run）`
    }
  }

  return items
}

export function blockingReadinessItems(items: RunReadinessItem[]): RunReadinessItem[] {
  return items.filter((item) => item.blocking && !item.ok)
}
