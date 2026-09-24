import { capSessionRecords, sortSessionsByRecent } from './session-records.js'
import type { CreateSessionInput, SessionManager } from './session-manager.js'
import { createThread } from './thread.js'
import type { ThreadManager } from './thread-manager.js'
import { createTraceRecord } from './trace.js'
import type { SessionSnapshot, SessionStatus, Thread, TraceRecord } from './types.js'

export function createMemorySessionManager(): SessionManager & ThreadManager {
  let sessions: SessionSnapshot[] = []
  let threads: Thread[] = []

  const touchThread = async (id: string): Promise<void> => {
    threads = threads.map((thread) =>
      thread.id === id ? { ...thread, updatedAt: Date.now() } : thread
    )
  }

  const sessionManager: SessionManager = {
    async listSessions() {
      return sortSessionsByRecent(sessions)
    },
    async getSession(id) {
      return sessions.find((session) => session.id === id)
    },
    async createSession(input: CreateSessionInput) {
      const now = Date.now()
      const session: SessionSnapshot = {
        id: crypto.randomUUID(),
        threadId: input.threadId,
        playbookId: input.playbookId,
        task: input.task,
        status: 'running',
        createdAt: now,
        updatedAt: now,
        page: input.page,
        records: [],
      }
      sessions = [session, ...sessions].slice(0, 50)
      if (input.threadId) await touchThread(input.threadId)
      return session
    },
    async continueSession(id, _task, page) {
      sessions = sessions.map((session) =>
        session.id === id
          ? {
              ...session,
              status: 'running',
              task: session.task,
              updatedAt: Date.now(),
              page: page ?? session.page,
            }
          : session
      )
      const threadId = sessions.find((session) => session.id === id)?.threadId
      if (threadId) await touchThread(threadId)
    },
    async appendRecord(sessionId, record) {
      let appended = false
      sessions = sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              updatedAt: Date.now(),
              records: session.records.some((item) => item.id === record.id)
                ? session.records
                : ((appended = true), capSessionRecords([...session.records, record])),
            }
          : session
      )
      if (appended) {
        const threadId = sessions.find((session) => session.id === sessionId)?.threadId
        if (threadId) await touchThread(threadId)
      }
    },
    async updateSessionPage(id, page) {
      sessions = sessions.map((session) =>
        session.id === id ? { ...session, page, updatedAt: Date.now() } : session
      )
    },
    async completeSession(id, status: SessionStatus) {
      sessions = sessions.map((session) =>
        session.id === id ? { ...session, status, updatedAt: Date.now() } : session
      )
      const threadId = sessions.find((session) => session.id === id)?.threadId
      if (threadId) await touchThread(threadId)
    },
    async deleteSession(id) {
      sessions = sessions.filter((session) => session.id !== id)
    },
    async clearSessions() {
      sessions = []
      threads = []
    },
    async listThreadRecords(threadId) {
      return sessions
        .filter((session) => session.threadId === threadId)
        .sort((a, b) => a.createdAt - b.createdAt)
        .flatMap((session) => session.records)
    },
    async getLatestThreadSession(threadId) {
      return sortSessionsByRecent(sessions.filter((session) => session.threadId === threadId))[0]
    },
    async linkSessionPlaybook(sessionId, playbookId) {
      sessions = sessions.map((session) =>
        session.id === sessionId ? { ...session, playbookId, updatedAt: Date.now() } : session
      )
    },
  }

  const threadManager: ThreadManager = {
    async listThreads() {
      return [...threads].sort((a, b) => b.updatedAt - a.updatedAt)
    },
    async createThread(title) {
      const thread = createThread(title)
      threads = [thread, ...threads].slice(0, 50)
      return thread
    },
    async updateThreadTitle(id, title) {
      const next = title.trim().slice(0, 80)
      if (!next) return
      threads = threads.map((thread) =>
        thread.id === id ? { ...thread, title: next, updatedAt: Date.now() } : thread
      )
    },
    async updateThreadMemory(id, memory, memoryAt) {
      threads = threads.map((thread) =>
        thread.id === id
          ? { ...thread, memory, memoryAt: memoryAt ?? Date.now(), updatedAt: Date.now() }
          : thread
      )
    },
    async updateThreadPlaybook(threadId, playbookId) {
      threads = threads.map((thread) =>
        thread.id === threadId
          ? { ...thread, lastPlaybookId: playbookId, updatedAt: Date.now() }
          : thread
      )
    },
    touchThread,
  }

  return { ...sessionManager, ...threadManager }
}

/** Append a trace record in tests without a full AgentSession instance. */
export function appendRecordForTest(
  manager: SessionManager,
  sessionId: string,
  input: { type: TraceRecord['type']; payload: TraceRecord['payload']; runId?: string }
): Promise<void> {
  const record = createTraceRecord({
    type: input.type,
    payload: input.payload,
    runId: input.runId ?? sessionId,
  })
  return manager.appendRecord(sessionId, record)
}
