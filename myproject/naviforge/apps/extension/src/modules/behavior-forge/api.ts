import { BEHAVIOR_RECORD } from './messages.js'
import type { BehaviorSessionMeta, BehaviorSessionRecord } from './types.js'

export async function behaviorRecord<T = unknown>(
  action: string,
  payload: Record<string, unknown> = {}
): Promise<T> {
  const message = { type: BEHAVIOR_RECORD, action, ...payload }
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const result = await chrome.runtime.sendMessage(message)
      if (result === undefined) throw new Error('Extension did not respond')
      return result as T
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error)
      const retryable =
        msg.includes('message channel closed') ||
        msg.includes('Receiving end does not exist') ||
        msg.includes('Extension did not respond')
      if (retryable && attempt === 0) {
        await new Promise((resolve) => setTimeout(resolve, 150))
        continue
      }
      throw error
    }
  }
  throw new Error('Extension did not respond')
}

export async function startRecording(tabId: number, captureDom?: boolean): Promise<string> {
  const res = await behaviorRecord<{ ok: boolean; sessionId?: string; error?: string }>('start', {
    tabId,
    ...(captureDom != null ? { captureDom } : {}),
  })
  if (!res.ok || !res.sessionId) throw new Error(res.error ?? 'start failed')
  return res.sessionId
}

export async function stopRecording(): Promise<BehaviorSessionRecord | null> {
  const res = await behaviorRecord<{ ok: boolean; record?: BehaviorSessionRecord | null }>('stop')
  return res.record ?? null
}

export async function recordingStatus(): Promise<{
  recording: boolean
  sessionId: string | null
  eventCount: number
}> {
  return behaviorRecord('status')
}

export async function listSessions(): Promise<BehaviorSessionMeta[]> {
  const res = await behaviorRecord<{ ok: boolean; sessions?: BehaviorSessionMeta[] }>('list')
  return res.sessions ?? []
}

export async function loadSession(id: string): Promise<BehaviorSessionRecord | null> {
  const res = await behaviorRecord<{ ok: boolean; record?: BehaviorSessionRecord }>('get', {
    sessionId: id,
  })
  return res.record ?? null
}

export async function deleteSession(id: string): Promise<void> {
  await behaviorRecord('delete', { sessionId: id })
}

export async function markSessionCloudId(id: string, cloudId: string): Promise<void> {
  await behaviorRecord('mark_cloud', { sessionId: id, cloudId })
}
