import { DEFAULT_PRIVACY, STORAGE, trimActivities, type PrivacySettings } from './settings'
import {
  capSessionRecords,
  createThread as createThreadEntity,
  deriveThreadSummary,
  sortSessionsByRecent,
  validateTraceRecord,
  type AgentSession,
  type Thread,
  type ThreadMemory,
  type TraceRecord,
} from './session-model'
import { appendWorkspaceLedger } from './local-workspace'
import { workspaceSlug } from '@naviforge/runtime'

export type { AgentSession, Thread as AgentThread, Thread, ThreadMemory, TraceRecord } from './session-model'
export { buildThreadContext } from './thread-model'

export type UserTaskExtras = {
  audioPath?: string
  audioLabel?: string
}

function normalizeThread(raw: Thread & { summary?: string; memory?: ThreadMemory }): Thread {
  return {
    id: raw.id,
    title: raw.title,
    memory: raw.memory ?? { goal: '', facts: [], constraints: [], openQuestions: [], lastOutcome: '' },
    lastPlaybookId: raw.lastPlaybookId,
    memoryAt: raw.memoryAt,
    createdAt: raw.createdAt,
    updatedAt: raw.updatedAt,
  }
}

function ledgerSession(session: AgentSession | undefined, record: TraceRecord): void {
  if (!session) return
  const threadId = session.threadId ?? session.id
  void appendWorkspaceLedger({
    threadId,
    slug: workspaceSlug(session.task),
    title: session.task,
    line: validateTraceRecord(record),
  })
}

async function loadSessions(): Promise<AgentSession[]> {
  const saved = await chrome.storage.local.get([STORAGE.sessions, STORAGE.privacy])
  const sessions = Array.isArray(saved[STORAGE.sessions])
    ? (saved[STORAGE.sessions] as AgentSession[])
    : []
  const privacy = {
    ...DEFAULT_PRIVACY,
    ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
  }
  const retained = trimActivities(
    sessions.map((session) => ({
      ...session,
      title: session.task,
      createdAt: session.updatedAt,
    })),
    privacy.retainHistoryDays
  )
  return retained.map((session) => ({
    id: session.id,
    kind: session.kind,
    threadId: session.threadId,
    parentSessionId: session.parentSessionId,
    parentRunId: session.parentRunId,
    leafRunId: session.leafRunId,
    playbookId: session.playbookId,
    status: session.status,
    task: session.task,
    createdAt: session.createdAt,
    updatedAt: session.updatedAt,
    page: session.page,
    records: session.records ?? [],
  }))
}

export function isContinuableSession(session: AgentSession): boolean {
  return session.kind !== 'leaf'
}

export async function listSessions(): Promise<AgentSession[]> {
  return sortSessionsByRecent((await loadSessions()).filter((session) => session.kind !== 'leaf'))
}

export async function getSession(id: string): Promise<AgentSession | undefined> {
  return (await loadSessions()).find((session) => session.id === id)
}

export async function listThreads(): Promise<Thread[]> {
  const saved = await chrome.storage.local.get(STORAGE.threads)
  const raw = Array.isArray(saved[STORAGE.threads])
    ? (saved[STORAGE.threads] as Array<Thread & { summary?: string }>)
    : []
  return raw.map(normalizeThread).sort((a, b) => b.updatedAt - a.updatedAt)
}

export async function createThread(title: string): Promise<Thread> {
  const thread = createThreadEntity(title)
  const threads = [thread, ...(await listThreads())].slice(0, 50)
  await chrome.storage.local.set({ [STORAGE.threads]: threads })
  return thread
}

export async function updateThreadPlaybook(threadId: string, playbookId: string): Promise<void> {
  const threads = (await listThreads()).map((thread) =>
    thread.id === threadId
      ? { ...thread, lastPlaybookId: playbookId, updatedAt: Date.now() }
      : thread
  )
  await chrome.storage.local.set({ [STORAGE.threads]: threads })
}

export async function linkSessionPlaybook(sessionId: string, playbookId: string): Promise<void> {
  const sessions = (await loadSessions()).map((session) =>
    session.id === sessionId ? { ...session, playbookId, updatedAt: Date.now() } : session
  )
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
}

export async function updateThreadMemory(
  id: string,
  memory: ThreadMemory,
  memoryAt?: number
): Promise<void> {
  const threads = (await listThreads()).map((thread) =>
    thread.id === id
      ? {
          ...thread,
          memory,
          memoryAt: memoryAt ?? Date.now(),
          updatedAt: Date.now(),
        }
      : thread
  )
  await chrome.storage.local.set({ [STORAGE.threads]: threads })
}

export async function updateThreadTitle(id: string, title: string): Promise<void> {
  const next = title.trim().slice(0, 80)
  if (!next) return
  const threads = (await listThreads()).map((thread) =>
    thread.id === id ? { ...thread, title: next, updatedAt: Date.now() } : thread
  )
  await chrome.storage.local.set({ [STORAGE.threads]: threads })
}

async function touchThread(id: string | undefined): Promise<void> {
  if (!id) return
  const threads = (await listThreads()).map((thread) =>
    thread.id === id ? { ...thread, updatedAt: Date.now() } : thread
  )
  await chrome.storage.local.set({ [STORAGE.threads]: threads })
}

export async function listThreadRecords(threadId: string): Promise<AgentSession['records']> {
  const sessions = await loadSessions()
  return sessions
    .filter((session) => session.threadId === threadId && session.kind !== 'leaf')
    .sort((a, b) => a.createdAt - b.createdAt)
    .flatMap((session) => session.records)
}

export async function getLatestThreadSession(threadId: string): Promise<AgentSession | undefined> {
  const sessions = (await loadSessions())
    .filter((session) => session.threadId === threadId && session.kind !== 'leaf')
    .sort((a, b) => b.updatedAt - a.updatedAt)
  return sessions[0]
}

export async function createLeafSession(input: {
  parentSessionId: string
  parentRunId: string
  leafRunId: string
  threadId?: string
  task: string
}): Promise<AgentSession> {
  const now = Date.now()
  const session: AgentSession = {
    id: crypto.randomUUID(),
    kind: 'leaf',
    parentSessionId: input.parentSessionId,
    parentRunId: input.parentRunId,
    leafRunId: input.leafRunId,
    threadId: input.threadId,
    task: input.task,
    status: 'running',
    createdAt: now,
    updatedAt: now,
    records: [],
  }
  const sessions = [session, ...(await loadSessions())].slice(0, 200)
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
  return session
}

export async function completeLeafSession(
  id: string,
  status: Extract<AgentSession['status'], 'success' | 'failed' | 'cancelled'>
): Promise<void> {
  await completeSession(id, status, '')
}

export async function continueSession(
  id: string,
  _task: string,
  page?: AgentSession['page'],
  _extras?: UserTaskExtras
): Promise<void> {
  const existing = await getSession(id)
  if (existing && !isContinuableSession(existing)) {
    throw new Error('leaf sessions cannot be continued')
  }
  const sessions = (await loadSessions()).map((session) =>
    session.id === id
      ? {
          ...session,
          status: 'running' as const,
          // Session title stays the first user goal; follow-ups like「继续」must not rename it.
          task: session.task,
          updatedAt: Date.now(),
          page: page ?? session.page,
          records: session.records,
        }
      : session
  )
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
  await touchThread(sessions.find((session) => session.id === id)?.threadId)
}

export async function createSession(
  task: string,
  threadId?: string,
  page?: AgentSession['page'],
  _extras?: UserTaskExtras
): Promise<AgentSession> {
  const now = Date.now()
  const session: AgentSession = {
    id: crypto.randomUUID(),
    threadId,
    task,
    status: 'running',
    createdAt: now,
    updatedAt: now,
    page,
    records: [],
  }
  const sessions = [session, ...(await loadSessions())].slice(0, 50)
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
  if (threadId) await touchThread(threadId)
  return session
}

export async function appendSessionRecord(id: string, record: TraceRecord): Promise<void> {
  const valid = validateTraceRecord(record)
  let appended = false
  const sessions = (await loadSessions()).map((session) =>
    session.id === id
      ? {
          ...session,
          updatedAt: Date.now(),
          records: session.records.some((item) => item.id === valid.id)
            ? session.records
            : (appended = true, capSessionRecords([...session.records, valid])),
        }
      : session
  )
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
  const session = sessions.find((item) => item.id === id)
  await touchThread(session?.threadId)
  if (appended) ledgerSession(session, valid)
}

export async function updateSessionPage(
  id: string,
  page: NonNullable<AgentSession['page']>
): Promise<void> {
  const sessions = (await loadSessions()).map((session) =>
    session.id === id ? { ...session, page, updatedAt: Date.now() } : session
  )
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
}

export async function completeSession(
  id: string,
  status: AgentSession['status'],
  _result: string
): Promise<void> {
  const sessions = (await loadSessions()).map((session) => {
    if (session.id !== id) return session
    return {
      ...session,
      status,
      updatedAt: Date.now(),
      records: session.records,
    }
  })
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
  const completed = sessions.find((session) => session.id === id)
  await touchThread(completed?.threadId)
}

export async function clearSessions(): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.sessions]: [], [STORAGE.threads]: [] })
}

export async function deleteSession(id: string): Promise<void> {
  const sessions = (await loadSessions()).filter((session) => session.id !== id)
  await chrome.storage.local.set({ [STORAGE.sessions]: sessions })
}

export function threadListSummary(thread: Thread): string {
  return deriveThreadSummary(thread.memory)
}
