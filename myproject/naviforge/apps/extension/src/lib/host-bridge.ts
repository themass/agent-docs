import type { ExternalMcpTool, LlmConfig } from '@naviforge/runtime'
import type { ToolResult } from '@naviforge/shared'

import { ensureLocalHelper, loadDiskMcp, persistMcpToDisk } from './local-workspace'
import {
  DEFAULT_HOST,
  DEFAULT_PRIVACY,
  STORAGE,
  loadCustomSkills,
  mergeInstalledSkills,
  seedMcpConnections,
  type HostSettings,
  type McpConnection,
} from './settings'
import { BUNDLED_SKILLS } from '../skills/catalog'

const ALARM = 'naviforge-host-poll'
let polling = false

type HostTask = {
  id: string
  instruction: string
  tabId?: number
  useNetwork: boolean
}

function safeHostUrl(value: string): string {
  const url = new URL(value)
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('Host bridge must use local HTTP on 127.0.0.1 or localhost')
  }
  return url.href.replace(/\/$/, '')
}

async function postResult(host: HostSettings, taskId: string, result: unknown): Promise<void> {
  await fetch(`${safeHostUrl(host.url)}/tasks/${encodeURIComponent(taskId)}/result`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${host.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(result),
  })
}

async function hostJson<T>(
  host: HostSettings,
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${safeHostUrl(host.url)}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${host.token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const body = (await response.json()) as { error?: string }
  if (!response.ok) throw new Error(body.error ?? `Host returned HTTP ${response.status}`)
  return body as T
}

async function syncMcpConnections(
  host: HostSettings,
  connections: McpConnection[]
): Promise<void> {
  await hostJson(host, '/mcp/connections', {
    method: 'POST',
    body: JSON.stringify({ connections }),
  })
}

export type HostMcpRuntime =
  | {
      ok: true
      mcpTools: ExternalMcpTool[]
      callMcpTool: (
        serverId: string,
        tool: string,
        args: Record<string, unknown>
      ) => Promise<ToolResult>
    }
  | { ok: false; reason: string }

export async function createHostMcpRuntime(): Promise<HostMcpRuntime> {
  const helper = await ensureLocalHelper()
  const saved = await chrome.storage.local.get([STORAGE.host, STORAGE.mcpConnections])
  const host = { ...DEFAULT_HOST, ...(saved[STORAGE.host] as Partial<HostSettings> | undefined) }
  if (!helper.ok || !host.token) {
    return {
      ok: false,
      reason: helper.error ?? '本机助手未运行：设置 → 工作区 启动后才会挂载 MCP',
    }
  }
  const connections = seedMcpConnections(saved[STORAGE.mcpConnections])
  const disk = await loadDiskMcp()
  const resolved = disk?.length ? disk : connections
  if (disk?.length) {
    await chrome.storage.local.set({ [STORAGE.mcpConnections]: disk })
  } else if (!Array.isArray(saved[STORAGE.mcpConnections]) || !(saved[STORAGE.mcpConnections] as unknown[]).length) {
    await chrome.storage.local.set({ [STORAGE.mcpConnections]: resolved })
    await persistMcpToDisk(resolved).catch(() => {})
  }
  try {
    await syncMcpConnections(host, resolved)
    const { tools } = await hostJson<{ tools: ExternalMcpTool[] }>(host, '/mcp/tools')
    if (!tools.length) {
      return {
        ok: false,
        reason:
          'Host 已连接，但当前无可用 MCP 工具（检查 MCP 连接是否启用；默认 Fetch 需本机可执行 npx）',
      }
    }
    return {
      ok: true,
      mcpTools: tools,
      callMcpTool: async (serverId, tool, args) => {
        try {
          const response = await hostJson<{ result: unknown }>(host, '/mcp/call', {
            method: 'POST',
            body: JSON.stringify({ serverId, tool, arguments: args }),
          })
          return { ok: true, data: response.result }
        } catch (error) {
          return {
            ok: false,
            error: { code: 'mcp_error', message: (error as Error).message, recoverable: true },
          }
        }
      },
    }
  } catch (error) {
    return {
      ok: false,
      reason: `Host MCP 不可用：${(error as Error).message}`,
    }
  }
}

async function execute(host: HostSettings, task: HostTask): Promise<void> {
  try {
    const saved = await chrome.storage.local.get([
      STORAGE.llm,
      STORAGE.disabledSkills,
      STORAGE.privacy,
    ])
    const llm = saved[STORAGE.llm] as LlmConfig | undefined
    if (!llm?.apiKey || !llm.baseURL || !llm.model) {
      throw new Error('Model configuration is incomplete in NaviForge Settings')
    }
    const privacy = {
      ...DEFAULT_PRIVACY,
      ...(saved[STORAGE.privacy] as Partial<typeof DEFAULT_PRIVACY> | undefined),
    }

    const tab = task.tabId
      ? await chrome.tabs.get(task.tabId)
      : (await chrome.tabs.query({ active: true, lastFocusedWindow: true }))[0]
    if (!tab?.id) throw new Error('No target Chrome tab is available')

    const disabled = Array.isArray(saved[STORAGE.disabledSkills])
      ? (saved[STORAGE.disabledSkills] as string[])
      : []
    const skills = mergeInstalledSkills(BUNDLED_SKILLS, await loadCustomSkills()).filter(
      (skill) => !disabled.includes(skill.manifest.id)
    )

    const { runSupervisor } = await import('./run-supervisor')
    const result = await runSupervisor.runHostPollTask({
      hostTaskId: task.id,
      instruction: task.instruction,
      tabId: tab.id,
      llm,
      useNetwork: task.useNetwork,
      privacy,
      skills,
    })
    await postResult(host, task.id, {
      ok: result.status === 'done',
      status: result.status,
      result: result.result,
    })
  } catch (error) {
    await postResult(host, task.id, {
      ok: false,
      status: 'error',
      error: (error as Error).message,
    }).catch(() => {})
  }
}

async function poll(): Promise<void> {
  if (polling) return
  polling = true
  try {
    const saved = await chrome.storage.local.get([STORAGE.host, STORAGE.mcpConnections])
    const host = { ...DEFAULT_HOST, ...(saved[STORAGE.host] as Partial<HostSettings> | undefined) }
    if (!host.enabled || !host.token) return
    const connections = Array.isArray(saved[STORAGE.mcpConnections])
      ? (saved[STORAGE.mcpConnections] as McpConnection[])
      : []
    await syncMcpConnections(host, connections)

    const response = await fetch(`${safeHostUrl(host.url)}/tasks/next`, {
      headers: { Authorization: `Bearer ${host.token}` },
    })
    if (response.status === 204) return
    if (!response.ok) throw new Error(`Host returned HTTP ${response.status}`)
    await execute(host, (await response.json()) as HostTask)
  } catch (error) {
    console.debug('NaviForge Host poll skipped:', (error as Error).message)
  } finally {
    polling = false
  }
}

export function startHostBridge(): void {
  chrome.alarms.create(ALARM, { periodInMinutes: 0.5 })
  chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === ALARM) void poll()
  })
  chrome.storage.onChanged.addListener((changes, area) => {
    if (
      area === 'local' &&
      (changes[STORAGE.host] || changes[STORAGE.mcpConnections])
    ) {
      void poll()
    }
  })
  void poll()
}
