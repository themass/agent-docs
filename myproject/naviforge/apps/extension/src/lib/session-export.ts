import type { SessionAuditExport } from '@naviforge/session'
import { deriveThreadSummary } from '@naviforge/session'

import { redactSessionText, type AgentSession } from './session-model'
import type { TraceRecord } from '@naviforge/session'
import type { AgentThread } from './thread-model'

export type { SessionAuditExport } from '@naviforge/session'

function redactPayload(value: unknown): unknown {
  if (typeof value === 'string') return redactSessionText(value)
  if (Array.isArray(value)) return value.map(redactPayload)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, redactPayload(item)]))
  }
  return value
}

export function buildSessionAuditExport(
  threads: AgentThread[],
  sessions: AgentSession[]
): SessionAuditExport {
  return {
    schemaVersion: 1,
    exportedAt: Date.now(),
    threads: threads.map((thread) => ({
      ...thread,
      memory: thread.memory,
    })),
    sessions: sessions.map((session) => ({
      ...session,
      records: session.records.map((record) => ({
        ...record,
        payload: redactPayload(record.payload) as TraceRecord['payload'],
      }) as TraceRecord),
    })),
  }
}

export function threadExportSummary(thread: AgentThread): string {
  return redactSessionText(deriveThreadSummary(thread.memory))
}

export function downloadSessionAudit(exportData: SessionAuditExport): void {
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `naviforge-audit-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
