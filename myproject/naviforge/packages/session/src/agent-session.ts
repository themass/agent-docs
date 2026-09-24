import { capSessionRecords } from './session-records.js'
import type { SessionManager } from './session-manager.js'
import { validateTraceRecord } from './trace.js'
import type { RunPhase, SessionEvent, SessionSnapshot, SessionStatus, TraceRecord } from './types.js'

export type AgentSessionHandle = {
  readonly id: string
  readonly threadId?: string
  readonly runId: string
  get snapshot(): SessionSnapshot
  get records(): readonly TraceRecord[]
  get phase(): RunPhase
  subscribe(listener: (event: SessionEvent) => void): () => void
  setPhase(phase: RunPhase): void
  append(record: TraceRecord): Promise<void>
  complete(status: SessionStatus): Promise<void>
}

/** Pi-style run facade: append records, emit events, delegate persistence. */
export class AgentSession implements AgentSessionHandle {
  readonly id: string
  readonly threadId?: string
  readonly runId: string

  private readonly manager: SessionManager
  private readonly listeners = new Set<(event: SessionEvent) => void>()
  private data: SessionSnapshot
  private _phase: RunPhase = 'idle'

  private constructor(manager: SessionManager, data: SessionSnapshot, runId: string) {
    this.manager = manager
    this.data = data
    this.id = data.id
    this.threadId = data.threadId
    this.runId = runId
    if (data.status === 'running') this._phase = 'running'
    if (data.status === 'waiting') this._phase = 'waiting_user'
    if (data.status === 'success') this._phase = 'succeeded'
    if (data.status === 'failed') this._phase = 'failed'
    if (data.status === 'cancelled') this._phase = 'cancelled'
  }

  static async open(manager: SessionManager, sessionId: string, runId?: string): Promise<AgentSession> {
    const data = await manager.getSession(sessionId)
    if (!data) throw new Error(`session not found: ${sessionId}`)
    return new AgentSession(manager, data, runId ?? sessionId)
  }

  static async create(
    manager: SessionManager,
    input: Parameters<SessionManager['createSession']>[0],
    runId?: string
  ): Promise<AgentSession> {
    const data = await manager.createSession(input)
    return new AgentSession(manager, data, runId ?? data.id)
  }

  get snapshot(): SessionSnapshot {
    return this.data
  }

  get records(): readonly TraceRecord[] {
    return this.data.records
  }

  get phase(): RunPhase {
    return this._phase
  }

  subscribe(listener: (event: SessionEvent) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  setPhase(phase: RunPhase): void {
    this._phase = phase
    this.emit({ type: 'phase', phase })
  }

  async append(record: TraceRecord): Promise<void> {
    const valid = validateTraceRecord(record)
    if (this.data.records.some((item) => item.id === valid.id)) return
    this.data = {
      ...this.data,
      updatedAt: Date.now(),
      records: capSessionRecords([...this.data.records, valid]),
    }
    await this.manager.appendRecord(this.id, valid)
    this.emit({ type: 'record', record: valid })
  }

  /** Apply a record already persisted elsewhere (e.g. background run owner). */
  ingest(record: TraceRecord): void {
    const valid = validateTraceRecord(record)
    if (this.data.records.some((item) => item.id === valid.id)) return
    this.data = {
      ...this.data,
      updatedAt: Date.now(),
      records: capSessionRecords([...this.data.records, valid]),
    }
    this.emit({ type: 'record', record: valid })
  }

  async complete(status: SessionStatus): Promise<void> {
    this.data = { ...this.data, status, updatedAt: Date.now() }
    await this.manager.completeSession(this.id, status)
    if (status === 'success') this.setPhase('succeeded')
    else if (status === 'failed') this.setPhase('failed')
    else if (status === 'cancelled') this.setPhase('cancelled')
    else if (status === 'waiting') this.setPhase('waiting_user')
  }

  private emit(event: SessionEvent): void {
    for (const listener of this.listeners) listener(event)
  }
}
