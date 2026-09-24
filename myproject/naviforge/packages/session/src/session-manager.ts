import type { SessionSnapshot, SessionStatus, TraceRecord } from './types.js'

export type CreateSessionInput = {
  task: string
  threadId?: string
  playbookId?: string
  page?: SessionSnapshot['page']
}

export type SessionManager = {
  listSessions(): Promise<SessionSnapshot[]>
  getSession(id: string): Promise<SessionSnapshot | undefined>
  createSession(input: CreateSessionInput): Promise<SessionSnapshot>
  continueSession(
    id: string,
    task: string,
    page?: SessionSnapshot['page']
  ): Promise<void>
  appendRecord(sessionId: string, record: TraceRecord): Promise<void>
  updateSessionPage(id: string, page: NonNullable<SessionSnapshot['page']>): Promise<void>
  completeSession(id: string, status: SessionStatus): Promise<void>
  deleteSession(id: string): Promise<void>
  clearSessions(): Promise<void>
  listThreadRecords(threadId: string): Promise<TraceRecord[]>
  getLatestThreadSession(threadId: string): Promise<SessionSnapshot | undefined>
  linkSessionPlaybook(sessionId: string, playbookId: string): Promise<void>
}
