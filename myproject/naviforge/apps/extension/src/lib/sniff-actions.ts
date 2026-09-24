import type { SniffApi, SniffProject, SniffSample } from './sniff-model'

type SniffResponse<T = unknown> =
  | { ok: true; data?: T; session?: { projectId: string }; live?: number }
  | { ok: false; error?: string }

type SniffStatusResponse = { ok: true; session?: { projectId: string }; live?: number } | { ok: false; error?: string }

async function sniffMessage<T = unknown>(
  action: string,
  payload: Record<string, unknown> = {}
): Promise<SniffResponse<T>> {
  return (await chrome.runtime.sendMessage({ type: 'SNIFF', action, ...payload })) as SniffResponse<T>
}

export async function sniffStatus(tabId: number): Promise<{
  session?: { projectId: string }
  live: number
}> {
  const res = (await chrome.runtime.sendMessage({
    type: 'SNIFF',
    action: 'status',
    tabId,
  })) as SniffStatusResponse
  if (!res.ok) return { live: 0 }
  return { session: res.session, live: res.live ?? 0 }
}

export async function sniffStart(projectId: string, tabId: number): Promise<void> {
  const res = await sniffMessage('start', { projectId, tabId })
  if (!res.ok) throw new Error(res.error ?? 'start failed')
}

export async function sniffStop(tabId: number, projectId?: string): Promise<{ apis: number; samples: number }> {
  const res = await sniffMessage<{ apis: number; samples: number }>('stop', { tabId, projectId })
  if (!res.ok) throw new Error(res.error ?? 'stop failed')
  return res.data ?? { apis: 0, samples: 0 }
}

export async function sniffFlush(
  tabId: number,
  projectId: string
): Promise<{ apis: number; samples: number }> {
  const res = await sniffMessage<{ apis: number; samples: number }>('flush', { tabId, projectId })
  if (!res.ok) throw new Error(res.error ?? 'flush failed')
  return res.data ?? { apis: 0, samples: 0 }
}

export async function sniffListProjects(): Promise<SniffProject[]> {
  const res = await sniffMessage<SniffProject[]>('listProjects')
  if (!res.ok) throw new Error(res.error ?? 'listProjects failed')
  return res.data ?? []
}

export async function sniffListApis(projectId: string): Promise<SniffApi[]> {
  const res = await sniffMessage<SniffApi[]>('listApis', { projectId })
  if (!res.ok) throw new Error(res.error ?? 'listApis failed')
  return res.data ?? []
}

export async function sniffListSamples(apiId: string): Promise<SniffSample[]> {
  const res = await sniffMessage<SniffSample[]>('listSamples', { apiId })
  if (!res.ok) throw new Error(res.error ?? 'listSamples failed')
  return res.data ?? []
}

export function downloadSniffJson(filename: string, json: string): void {
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

export async function getActiveTab(): Promise<chrome.tabs.Tab | undefined> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  return tab
}

export function hostFromUrl(url?: string): string {
  if (!url) return ''
  try {
    return new URL(url).hostname
  } catch {
    return ''
  }
}
