import { AgentSession, appendUniqueRecords, capSessionRecords, createTraceRecord, type SessionManager, type TraceRecord } from '@naviforge/session'

import { createChromeSessionManager } from '../lib/chrome-session-manager'

export type LiveSessionBridge = {
  appendLocal(
    type: TraceRecord['type'],
    payload: TraceRecord['payload'],
    trace?: { taskId?: string; turn?: number }
  ): void
  ingest(record: TraceRecord): void
  persist(input: { type: TraceRecord['type']; payload: TraceRecord['payload'] }): void
  bindSession(sessionId: string | null): Promise<void>
  dispose(): void
}

type LiveSessionOptions = {
  getSessionId(): string | null
  /** Active background run id — keeps preflight notes on the same timeline as agent steps. */
  getRunId?: () => string | null
  onRecords(records: TraceRecord[]): void
  manager?: SessionManager
}

function resolveRunId(options: LiveSessionOptions): string {
  const runId = options.getRunId?.()
  if (runId) return runId
  const sessionId = options.getSessionId()
  return sessionId ? `local:${sessionId}` : 'local:pending'
}

function primaryRunId(records: readonly TraceRecord[]): string | undefined {
  return records.find((record) => !record.runId.startsWith('local:'))?.runId
}

function coalesceRunId(record: TraceRecord, runId?: string): TraceRecord {
  if (!runId || !record.runId.startsWith('local:')) return record
  return { ...record, runId }
}

/** Pi-style facade: subscribe to `AgentSession`, ingest background records without double-write. */
export function createLiveSessionBridge(options: LiveSessionOptions): LiveSessionBridge {
  const manager = options.manager ?? createChromeSessionManager()
  let live: AgentSession | null = null
  let unsubscribe: (() => void) | null = null
  let localRecords: TraceRecord[] = []

  function publish(records: readonly TraceRecord[]): void {
    localRecords = [...records]
    options.onRecords(localRecords)
  }

  function ingestLocal(record: TraceRecord): void {
    if (live) {
      live.ingest(record)
      return
    }
    publish(appendUniqueRecords(localRecords, record))
  }

  return {
    appendLocal(type, payload, trace): void {
      ingestLocal(
        createTraceRecord({
          type,
          payload,
          runId: resolveRunId(options),
          taskId: trace?.taskId,
          turn: trace?.turn,
        })
      )
    },
    ingest(record): void {
      ingestLocal(record)
    },
    persist(input): void {
      const sessionId = options.getSessionId()
      if (!sessionId) return
      const record = createTraceRecord({ ...input, runId: resolveRunId(options) })
      if (live) {
        void live.append(record)
        return
      }
      publish(capSessionRecords([...localRecords, record]))
      void manager.appendRecord(sessionId, record)
    },
    async bindSession(sessionId): Promise<void> {
      unsubscribe?.()
      unsubscribe = null
      const orphanLocal = [...localRecords]
      live = null
      if (!sessionId) {
        localRecords = []
        options.onRecords([])
        return
      }
      live = await AgentSession.open(manager, sessionId)
      const sessionIds = new Set(live.records.map((record) => record.id))
      const runId = primaryRunId(live.records) ?? options.getRunId?.() ?? undefined
      const extras = orphanLocal
        .filter((record) => !sessionIds.has(record.id))
        .map((record) => coalesceRunId(record, runId))
      publish(capSessionRecords([...live.records, ...extras]))
      unsubscribe = live.subscribe((event) => {
        if (event.type === 'record') publish(live!.records)
      })
    },
    dispose(): void {
      unsubscribe?.()
      unsubscribe = null
      live = null
    },
  }
}
