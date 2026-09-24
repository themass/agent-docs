import type { SessionManager } from '@naviforge/session'

import {
  appendSessionRecord,
  completeSession,
  continueSession,
  createSession,
  deleteSession,
  clearSessions,
  getLatestThreadSession,
  getSession,
  linkSessionPlaybook,
  listSessions,
  listThreadRecords,
  updateSessionPage,
} from './session-store'

/** Chrome storage adapter for live `AgentSession` in the side panel. */
export function createChromeSessionManager(): SessionManager {
  return {
    listSessions,
    getSession,
    createSession: (input) => createSession(input.task, input.threadId, input.page),
    continueSession,
    appendRecord: appendSessionRecord,
    updateSessionPage,
    completeSession: (id, status) => completeSession(id, status, status),
    deleteSession,
    clearSessions,
    listThreadRecords,
    getLatestThreadSession,
    linkSessionPlaybook,
  }
}
