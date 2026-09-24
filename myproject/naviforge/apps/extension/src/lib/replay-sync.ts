import { isNewApiLoggedIn, loadNewApiAuth, normalizePortalBase } from './newapi-auth'
import type { BehaviorSessionMeta, BehaviorSessionRecord } from '../modules/behavior-forge/types'

export type CloudReplayMeta = {
  id: string
  title: string
  originUrl: string
  durationMs: number
  eventCount: number
  hasRrweb: boolean
  createdAt: number
}

type ApiEnvelope<T> = { success: boolean; message?: string; data?: T }

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const auth = await loadNewApiAuth()
  if (!isNewApiLoggedIn(auth) || !auth.accessToken) {
    throw new Error('请先登录 NewAPI')
  }
  const portal = normalizePortalBase(auth.portalBase)
  const res = await fetch(`${portal}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${auth.accessToken}`,
      ...(init?.headers ?? {}),
    },
  })
  const body = (await res.json().catch(() => ({}))) as ApiEnvelope<T>
  if (!res.ok || body.success === false) {
    throw new Error(body.message ?? `请求失败 (${res.status})`)
  }
  return body.data as T
}

export async function uploadReplayToCloud(record: BehaviorSessionRecord): Promise<string> {
  const data = await authFetch<{ id: string }>('/api/plugin/replay/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: record.id,
      title: record.title,
      originUrl: record.originUrl,
      durationMs: record.durationMs,
      viewport: record.viewport,
      events: record.events,
      rrwebEvents: record.rrwebEvents ?? [],
    }),
  })
  if (!data?.id) throw new Error('上传响应无效')
  return data.id
}

export async function listCloudReplays(): Promise<CloudReplayMeta[]> {
  const data = await authFetch<{ sessions: CloudReplayMeta[] }>('/api/plugin/replay/sessions')
  return data?.sessions ?? []
}

export async function downloadCloudReplay(id: string): Promise<BehaviorSessionRecord> {
  const data = await authFetch<{ record: BehaviorSessionRecord }>(
    `/api/plugin/replay/sessions/${encodeURIComponent(id)}`
  )
  if (!data?.record) throw new Error('云端会话不存在')
  return data.record
}

export async function deleteCloudReplay(id: string): Promise<void> {
  await authFetch(`/api/plugin/replay/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' })
}
