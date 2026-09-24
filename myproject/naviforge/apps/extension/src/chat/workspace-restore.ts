import { useEffect } from 'react'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'
import type { MutableRefObject } from 'react'
import type { TraceRecord } from '@naviforge/session'

import type { AgentSession } from '../lib/session-model'
import { hasResumeRequest, STORAGE, type ResumeSessionPayload } from '../lib/settings'
import {
  canRestoreTabWorkspace,
  readTabWorkspace,
  writeTabWorkspace,
  type TabWorkspace,
  type TabWorkspaces,
} from '../lib/tab-workspace'
import { isToolkitPageUrl } from '../lib/toolkit-actions'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import type { AgentThread } from '../lib/thread-model'

export type WorkspaceRestoreDeps = {
  workspaceRef: MutableRefObject<TabWorkspace>
  workspaceTabRef: MutableRefObject<number | null>
  workspaceGenerationRef: MutableRefObject<number>
  resumeLockRef: MutableRefObject<boolean>
  runningRef: MutableRefObject<boolean>
  tabRef: MutableRefObject<number | null>
  loadedThreadRef: MutableRefObject<string>
  sessionRef: MutableRefObject<string | null>
  currentTaskRef: MutableRefObject<{ id: string; text: string } | null>
  pendingTasksRef: MutableRefObject<Array<{ id: string; text: string }>>
  getSession(sessionId: string): Promise<AgentSession | undefined>
  adoptTab(tab: chrome.tabs.Tab): void
  syncPendingTasks(tasks: Array<{ id: string; text: string }>): void
  setThreads(value: AgentThread[]): void
  setActiveThreadId(value: string): void
  setTask(value: string): void
  setRecords(value: TraceRecord[]): void
  setTraceOpen(value: boolean): void
  setStatus(value: WorkspaceRunStatus): void
  setTargetTab(value: {
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null): void
  setCurrentTask(value: { id: string; text: string } | null): void
  bindLiveSession(sessionId: string | null): Promise<void>
  listThreads(): Promise<AgentThread[]>
  listThreadRecords(threadId: string): Promise<TraceRecord[]>
}

export function createWorkspaceRestore(deps: WorkspaceRestoreDeps) {
  async function persistWorkspace(tabId: number): Promise<void> {
    const saved = await chrome.storage.session.get(STORAGE.tabWorkspaces)
    const workspaces = (saved[STORAGE.tabWorkspaces] as TabWorkspaces | undefined) ?? {}
    await chrome.storage.session.set({
      [STORAGE.tabWorkspaces]: writeTabWorkspace(workspaces, tabId, deps.workspaceRef.current),
    })
  }

  async function applyResumeSession(resume: ResumeSessionPayload | undefined): Promise<void> {
    if (!hasResumeRequest(resume)) return
    const generation = ++deps.workspaceGenerationRef.current
    deps.resumeLockRef.current = true
    try {
      const session = resume.sessionId ? await deps.getSession(resume.sessionId) : undefined
      if (generation !== deps.workspaceGenerationRef.current) return
      const restored = session?.records ?? []
      const threadId =
        resume.threadId ?? session?.threadId ?? deps.workspaceRef.current.activeThreadId
      const task = resume.task ?? session?.task ?? deps.workspaceRef.current.task

      deps.setActiveThreadId(threadId)
      deps.setTask(task)
      if (session) {
        deps.sessionRef.current = session.id
        deps.setRecords(restored)
        await deps.bindLiveSession(session.id)
        deps.setTraceOpen(true)
        deps.setStatus(
          session.status === 'success'
            ? RUN_STATUS.COMPLETED
            : session.status === 'failed'
              ? RUN_STATUS.FAILED
              : RUN_STATUS.IDLE
        )
      }

      let targetTab = deps.workspaceRef.current.targetTab
      const page = resume.page
      if (page) {
        const adopt = (tab: chrome.tabs.Tab): void => {
          if (tab.id == null) return
          deps.tabRef.current = tab.id
          deps.workspaceTabRef.current = tab.id
          targetTab = { id: tab.id, url: tab.url, title: tab.title }
          deps.setTargetTab(targetTab)
        }
        try {
          adopt(await chrome.tabs.get(page.tabId))
        } catch {
          if (page.url) adopt(await chrome.tabs.create({ url: page.url, active: true }))
        }
        if (generation !== deps.workspaceGenerationRef.current) return
      }

      const workspace: TabWorkspace = {
        task,
        activeThreadId: threadId,
        traceOpen: Boolean(session),
        targetTab,
      }
      deps.workspaceRef.current = workspace
      await chrome.storage.local.remove(STORAGE.resumeSession)
      if (deps.tabRef.current != null) {
        const saved = await chrome.storage.session.get(STORAGE.tabWorkspaces)
        if (generation !== deps.workspaceGenerationRef.current) return
        const workspaces = (saved[STORAGE.tabWorkspaces] as TabWorkspaces | undefined) ?? {}
        await chrome.storage.session.set({
          [STORAGE.tabWorkspaces]: writeTabWorkspace(workspaces, deps.tabRef.current, workspace),
        })
      }
    } finally {
      if (generation === deps.workspaceGenerationRef.current) deps.resumeLockRef.current = false
    }
  }

  function applyWorkspaceSnapshot(workspace: TabWorkspace): void {
    deps.setTask(workspace.task)
    deps.setActiveThreadId(workspace.activeThreadId)
    deps.setTraceOpen(workspace.traceOpen)
    deps.setTargetTab(workspace.targetTab)
    deps.syncPendingTasks([])
    deps.setCurrentTask(null)
    deps.currentTaskRef.current = null
    deps.tabRef.current = workspace.targetTab?.id ?? null
    if (workspace.activeThreadId) {
      void deps.listThreadRecords(workspace.activeThreadId).then((threadRecords) => {
        if (threadRecords.length) deps.setRecords(threadRecords)
      })
    }
  }

  return { persistWorkspace, applyResumeSession, applyWorkspaceSnapshot }
}

export function useWorkspaceRestoreEffects(
  deps: WorkspaceRestoreDeps & ReturnType<typeof createWorkspaceRestore>
): void {
  const { persistWorkspace, applyResumeSession, applyWorkspaceSnapshot } = deps

  useEffect(() => {
    const generation = deps.workspaceGenerationRef.current
    void Promise.all([deps.listThreads(), chrome.storage.local.get(STORAGE.resumeSession)]).then(
      async ([stored, saved]) => {
        if (generation !== deps.workspaceGenerationRef.current) return
        deps.setThreads(stored)
        const resume = saved[STORAGE.resumeSession] as ResumeSessionPayload | undefined
        if (hasResumeRequest(resume)) {
          await applyResumeSession(resume)
          return
        }
        if (
          generation !== deps.workspaceGenerationRef.current ||
          deps.runningRef.current ||
          deps.resumeLockRef.current
        ) {
          return
        }
        if (stored.length) deps.setActiveThreadId(stored[0]!.id)
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
        if (
          !tab?.id ||
          !canRestoreTabWorkspace({
            generation,
            currentGeneration: deps.workspaceGenerationRef.current,
            running: deps.runningRef.current,
            resumeLocked: deps.resumeLockRef.current,
            hasResumeRequest: false,
          })
        ) {
          return
        }
        deps.workspaceTabRef.current = tab.id
        const workspaces =
          ((await chrome.storage.session.get(STORAGE.tabWorkspaces))[STORAGE.tabWorkspaces] as
            | TabWorkspaces
            | undefined) ?? {}
        if (
          !canRestoreTabWorkspace({
            generation,
            currentGeneration: deps.workspaceGenerationRef.current,
            running: deps.runningRef.current,
            resumeLocked: deps.resumeLockRef.current,
            hasResumeRequest: false,
          })
        ) {
          return
        }
        const workspace = readTabWorkspace(workspaces, tab.id)
        if (!workspace) {
          deps.adoptTab(tab)
          return
        }
        applyWorkspaceSnapshot(workspace)
      }
    )
    const onStorageChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ): void => {
      const resume = changes[STORAGE.resumeSession]?.newValue as ResumeSessionPayload | undefined
      if (area !== 'local' || !hasResumeRequest(resume)) return
      void applyResumeSession(resume)
    }
    chrome.storage.onChanged.addListener(onStorageChange)
    return () => chrome.storage.onChanged.removeListener(onStorageChange)
  }, [])

  useEffect(() => {
    const restoreWorkspace = async (tabId: number): Promise<void> => {
      const generation = deps.workspaceGenerationRef.current
      const pending = await chrome.storage.local.get(STORAGE.resumeSession)
      if (
        !canRestoreTabWorkspace({
          generation,
          currentGeneration: deps.workspaceGenerationRef.current,
          running: deps.runningRef.current,
          resumeLocked: deps.resumeLockRef.current,
          hasResumeRequest: hasResumeRequest(
            pending[STORAGE.resumeSession] as ResumeSessionPayload | undefined
          ),
        })
      ) {
        return
      }
      const saved = await chrome.storage.session.get(STORAGE.tabWorkspaces)
      if (
        !canRestoreTabWorkspace({
          generation,
          currentGeneration: deps.workspaceGenerationRef.current,
          running: deps.runningRef.current,
          resumeLocked: deps.resumeLockRef.current,
          hasResumeRequest: false,
        })
      ) {
        return
      }
      const workspaces = (saved[STORAGE.tabWorkspaces] as TabWorkspaces | undefined) ?? {}
      const workspace = readTabWorkspace(workspaces, tabId)
      if (!workspace) {
        try {
          const tab = await chrome.tabs.get(tabId)
          if (!deps.runningRef.current) deps.adoptTab(tab)
        } catch {
          /* tab closed */
        }
        return
      }
      applyWorkspaceSnapshot(workspace)
    }
    const onActivated = (info: chrome.tabs.TabActiveInfo): void => {
      // Agent run pins control tab + live timeline — ignore browser tab switches until it finishes.
      if (deps.runningRef.current) return
      const previous = deps.workspaceTabRef.current
      if (previous != null && previous !== info.tabId) void persistWorkspace(previous)
      deps.workspaceTabRef.current = info.tabId
      void restoreWorkspace(info.tabId)
    }
    chrome.tabs.onActivated.addListener(onActivated)
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated)
      if (deps.workspaceTabRef.current != null) void persistWorkspace(deps.workspaceTabRef.current)
    }
  }, [])
}

export function useTargetTabSync(
  tabRef: MutableRefObject<number | null>,
  runningRef: MutableRefObject<boolean>,
  setTargetTab: (value: TabWorkspace['targetTab']) => void
): void {
  useEffect(() => {
    const syncTarget = async (tabId: number) => {
      if (runningRef.current) return
      if (tabRef.current !== tabId) return
      try {
        const tab = await chrome.tabs.get(tabId)
        setTargetTab({ id: tab.id!, url: tab.url, title: tab.title })
      } catch {
        setTargetTab({ id: tabId })
      }
    }
    const onActivated = (info: chrome.tabs.TabActiveInfo) => {
      if (tabRef.current === info.tabId) void syncTarget(info.tabId)
    }
    const onUpdated = (tabId: number, _change: chrome.tabs.TabChangeInfo, tab: chrome.tabs.Tab) => {
      if (runningRef.current) return
      if (tabRef.current === tabId) {
        setTargetTab({ id: tabId, url: tab.url, title: tab.title })
      }
    }
    chrome.tabs.onActivated.addListener(onActivated)
    chrome.tabs.onUpdated.addListener(onUpdated)
    return () => {
      chrome.tabs.onActivated.removeListener(onActivated)
      chrome.tabs.onUpdated.removeListener(onUpdated)
    }
  }, [])
}

export function adoptToolkitTab(
  tab: chrome.tabs.Tab,
  tabRef: MutableRefObject<number | null>,
  setTargetTab: (value: {
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null) => void
): void {
  if (tab.id == null || !isToolkitPageUrl(tab.url)) return
  tabRef.current = tab.id
  setTargetTab({ id: tab.id, url: tab.url, title: tab.title, windowId: tab.windowId })
  void safeRuntimeSendMessage({ type: 'NETWORK', action: 'bind_session', tabId: tab.id })
}
