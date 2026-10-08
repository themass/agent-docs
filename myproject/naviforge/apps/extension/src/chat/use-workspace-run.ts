import { useEffect, useMemo, useRef, useState, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import {
  createHitlGate,
  createMessageQueue,
  createPauseController,
  type LlmConfig,
  type QueuedTask,
} from '@naviforge/runtime'
import { type TraceRecord } from '@naviforge/session'
import { type Skill } from '@naviforge/skill-runtime'

import {
  completeSession,
  getSession,
  listThreadRecords,
  listThreads,
} from '../lib/session-store'
import {
  getActiveModelProfile,
  profileToLlmConfig,
  type ModelProfilesStore,
} from '../lib/llm-profiles'
import { mergeInstalledSkills } from '../lib/settings'
import type { TabWorkspace } from '../lib/tab-workspace'
import { type RunReadinessItem } from '../lib/run-readiness'
import { BUNDLED_SKILLS } from '../skills/catalog'
import { createLiveSessionBridge } from './live-session'
import { persistThreadMemory as saveThreadMemory } from './thread-store'
import { createAgentRunController, type AgentRunMessage } from './agent-run-controller'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import { DEFAULT_LLM, type PickedElement, type TopVideo } from './workspace-helpers'
import type { WorkspaceRunOutcome } from './run-outcome'
import { createWorkspaceRecordHandler } from './workspace-record-handler'
import {
  createWorkspaceRestore,
  useTargetTabSync,
  useWorkspaceRestoreEffects,
} from './workspace-restore'
import { createTabControl } from './workspace-tab-control'
import { createQueueControl } from './workspace-queue'
import { createRunLifecycle } from './workspace-run'
import { createWorkspaceRunWire } from './workspace-run-wire'
import { useWorkspaceAgentSync } from './workspace-effects'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'

export type UseWorkspaceRunDeps = {
  task: string
  setTask(value: string | ((current: string) => string)): void
  threads: import('../lib/thread-model').AgentThread[]
  setThreads: Dispatch<SetStateAction<import('../lib/thread-model').AgentThread[]>>
  activeThreadId: string
  setActiveThreadId(value: string): void
  targetTab: {
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null
  setTargetTab(value: {
    id: number
    url?: string
    title?: string
    windowId?: number
  } | null): void
  setAllTabs(
    value: Array<{ id: number; title?: string; url?: string; active: boolean; windowId?: number }>
  ): void
  setTabPickerOpen(value: boolean): void
  pageAskBusy: boolean
  setPageAskBusy(value: boolean): void
  pageAskAbortRef: MutableRefObject<AbortController | null>
  voiceRef: MutableRefObject<{ dataUrl: string; path?: string; label: string } | null>
  imageRef: MutableRefObject<{ dataUrl: string; label: string } | null>
  pendingVoiceByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; path?: string; label: string }>
  >
  pendingImageByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; label: string }>
  >
  explainAfterPickRef: MutableRefObject<boolean>
  setPickedElement(value: PickedElement | null): void
  setPickingElement(value: boolean): void
  setQueuedExplain(value: PickedElement | null): void
  setImageAttachment(value: { dataUrl: string; label: string } | null): void
  setVoiceAttachment(value: { dataUrl: string; path?: string; label: string } | null): void
  setPrivacyToast(value: string | null): void
  customSkills: Skill[]
  disabledSkills: string[]
  modelProfiles: ModelProfilesStore | null
  useNetwork: boolean
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  hitlPolicy: 'strict' | 'balanced' | 'permissive'
  rollbackUrlDrift: boolean
  captureNetworkBodies: boolean
  allowMainProbe: boolean
  visionEnabled: boolean
  maxAgentSteps: number
  sameFailureLimit: number
  runTimeoutMs: number
  tokenBudget: number
  maxInputTokens: number
  enforceSkillToolAllowlist: boolean
}

export function useWorkspaceRun(deps: UseWorkspaceRunDeps) {
  const [records, setRecords] = useState<TraceRecord[]>([])
  const [status, setStatus] = useState<WorkspaceRunStatus>(RUN_STATUS.IDLE)
  const [statusDetail, setStatusDetail] = useState<string | null>(null)
  const [liveFeed, setLiveFeed] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null)
  const [paused, setPaused] = useState(false)
  const [queuePending, setQueuePending] = useState({ steering: 0, followUp: 0 })
  const [pendingTasks, setPendingTasks] = useState<QueuedTask[]>([])
  const [currentTask, setCurrentTask] = useState<QueuedTask | null>(null)
  const [awaitingQuestion, setAwaitingQuestion] = useState<string | null>(null)
  const [blockedQuestions, setBlockedQuestions] = useState<string[]>([])
  const [lastRunFailed, setLastRunFailed] = useState(false)
  const [traceOpen, setTraceOpen] = useState(false)
  const [runOutcome, setRunOutcome] = useState<WorkspaceRunOutcome | null>(null)
  const [topVideos, setTopVideos] = useState<TopVideo[]>([])
  const [resultsMarked, setResultsMarked] = useState(false)
  const [resultsStale, setResultsStale] = useState(false)
  const [listWarnings, setListWarnings] = useState<{ missed?: string[]; offscreen?: string[]; shortfall?: string }>(
    {}
  )
  const [pageSignalsPreview, setPageSignalsPreview] = useState<string | null>(null)
  const [tokenUsage, setTokenUsage] = useState<{
    lastPrompt: number
    lastCompletion: number
    runTotal: number
  } | null>(null)
  const [readinessItems, setReadinessItems] = useState<RunReadinessItem[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const pauseRef = useRef(createPauseController())
  const queueRef = useRef(createMessageQueue())
  const hitlRef = useRef(createHitlGate())
  const pendingTasksRef = useRef<QueuedTask[]>([])
  const currentTaskRef = useRef<QueuedTask | null>(null)
  const processLockRef = useRef(false)
  const activityRef = useRef<string | null>(null)
  const activeRunIdRef = useRef<string | null>(null)
  const sessionRef = useRef<string | null>(null)
  const tabRef = useRef<number | null>(null)
  const runningRef = useRef(false)
  const workspaceRef = useRef<TabWorkspace>({
    task: '',
    activeThreadId: '',
    traceOpen: false,
    targetTab: null,
  })
  const workspaceTabRef = useRef<number | null>(null)
  const workspaceGenerationRef = useRef(0)
  const resumeLockRef = useRef(false)
  const loadedThreadRef = useRef('')
  const lastRunModeRef = useRef<string | undefined>(undefined)

  const agentRun = useMemo(
    () =>
      createAgentRunController(async <T>(message: AgentRunMessage) => {
        const response = await safeRuntimeSendMessage<T>(message)
        return (response ?? {}) as T
      }),
    []
  )

  const liveSessionRef = useRef(
    createLiveSessionBridge({
      getSessionId: () => sessionRef.current,
      getRunId: () => activeRunIdRef.current,
      onRecords: (next) => setRecords([...next]),
    })
  )

  function push(line: string): void {
    liveSessionRef.current.appendLocal('run.log', { message: line })
  }

  const tabControl = createTabControl({
    tabRef,
    runningRef,
    explainAfterPickRef: deps.explainAfterPickRef,
    setTargetTab: deps.setTargetTab,
    setPickingElement: deps.setPickingElement,
    setPickedElement: deps.setPickedElement,
    setTask: deps.setTask,
    setAllTabs: deps.setAllTabs,
    setTabPickerOpen: deps.setTabPickerOpen,
    setRunOutcome,
    push,
  })

  const wire = {
    startRun: null as ((taskItem: QueuedTask) => Promise<void>) | null,
  }

  const queueControl = createQueueControl({
    queueRef,
    pendingTasksRef,
    processLockRef,
    runningRef,
    currentTaskRef,
    voiceRef: deps.voiceRef,
    imageRef: deps.imageRef,
    pendingVoiceByTaskRef: deps.pendingVoiceByTaskRef,
    pendingImageByTaskRef: deps.pendingImageByTaskRef,
    activityRef,
    activeRunIdRef,
    sessionRef,
    markSessionComplete: (sessionId, status, result) =>
      completeSession(sessionId, status, result ?? ''),
    task: deps.task,
    running,
    status,
    awaitingQuestion,
    setTask: deps.setTask,
    setVoiceAttachment: deps.setVoiceAttachment,
    setImageAttachment: deps.setImageAttachment,
    setPendingTasks,
    setQueuePending,
    setRunning,
    setRunStartedAt,
    setCurrentTask,
    setStatus,
    setStatusDetail,
    setLiveFeed,
    setAwaitingQuestion,
    setRunOutcome,
    push,
    recordSession: (record) => liveSessionRef.current.persist(record),
    appendLocal: liveSessionRef.current.appendLocal,
    agentRun,
    startRun: (taskItem) => wire.startRun!(taskItem),
  })

  const activeProfile = deps.modelProfiles ? getActiveModelProfile(deps.modelProfiles) : null
  const llm: LlmConfig = useMemo(
    () =>
      activeProfile
        ? profileToLlmConfig(activeProfile)
        : { baseURL: DEFAULT_LLM.baseURL, apiKey: '', model: DEFAULT_LLM.model },
    [activeProfile]
  )

  const allSkills = mergeInstalledSkills(BUNDLED_SKILLS, deps.customSkills)
  const enabledSkills = allSkills.filter((skill) => !deps.disabledSkills.includes(skill.manifest.id))

  wire.startRun = createWorkspaceRunWire({
    llm,
    customSkills: deps.customSkills,
    disabledSkills: deps.disabledSkills,
    enforceSkillToolAllowlist: deps.enforceSkillToolAllowlist,
    useNetwork: deps.useNetwork,
    captureNetworkBodies: deps.captureNetworkBodies,
    allowDomInject: deps.allowDomInject,
    allowNetworkIntercept: deps.allowNetworkIntercept,
    visionEnabled: deps.visionEnabled,
    maxAgentSteps: deps.maxAgentSteps,
    sameFailureLimit: deps.sameFailureLimit,
    runTimeoutMs: deps.runTimeoutMs,
    tokenBudget: deps.tokenBudget,
    maxInputTokens: deps.maxInputTokens,
    hitlPolicy: deps.hitlPolicy,
    rollbackUrlDrift: deps.rollbackUrlDrift,
    threads: deps.threads,
    activeThreadId: deps.activeThreadId,
    workspaceGenerationRef,
    resumeLockRef,
    abortRef,
    pauseRef,
    queueRef,
    hitlRef,
    pendingTasksRef,
    pendingVoiceByTaskRef: deps.pendingVoiceByTaskRef,
    pendingImageByTaskRef: deps.pendingImageByTaskRef,
    runningRef,
    currentTaskRef,
    sessionRef,
    activityRef,
    activeRunIdRef,
    loadedThreadRef,
    setReadinessItems,
    setQueuePending,
    setAwaitingQuestion,
    setBlockedQuestions,
    setLastRunFailed,
    setRunOutcome,
    setTopVideos,
    setResultsMarked,
    setResultsStale,
    setListWarnings,
    setTokenUsage,
    setTraceOpen,
    setPrivacyToast: deps.setPrivacyToast,
    setPaused,
    setRunning,
    setRunStartedAt,
    setCurrentTask,
    setTask: deps.setTask,
    setStatus,
    setLiveFeed,
    setThreads: deps.setThreads,
    setActiveThreadId: deps.setActiveThreadId,
    push,
    bindLiveSession: (sessionId) => liveSessionRef.current.bindSession(sessionId),
    appendLocal: liveSessionRef.current.appendLocal,
    recordSession: (record) => liveSessionRef.current.persist(record),
    syncPendingTasks: queueControl.syncPendingTasks,
    abortUnstarted: queueControl.abortUnstarted,
    bindActiveTab: tabControl.bindActiveTab,
    listThreadRecords,
  })

  const restore = createWorkspaceRestore({
    workspaceRef,
    workspaceTabRef,
    workspaceGenerationRef,
    resumeLockRef,
    runningRef,
    tabRef,
    loadedThreadRef,
    sessionRef,
    currentTaskRef,
    pendingTasksRef,
    getSession,
    adoptTab: tabControl.adoptTab,
    syncPendingTasks: queueControl.syncPendingTasks,
    setThreads: deps.setThreads,
    setActiveThreadId: deps.setActiveThreadId,
    setTask: deps.setTask,
    setRecords,
    setTraceOpen,
    setStatus,
    setTargetTab: deps.setTargetTab,
    setCurrentTask,
    listThreads,
    listThreadRecords,
    bindLiveSession: (sessionId) => liveSessionRef.current.bindSession(sessionId),
  })

  async function persistThreadMemory(
    taskText: string,
    resultText: string,
    mode?: string,
    opts?: { setGoal?: boolean }
  ): Promise<void> {
    const threadId = deps.activeThreadId || workspaceRef.current.activeThreadId
    if (!threadId) return
    const thread = await saveThreadMemory({
      threadId,
      task: taskText,
      result: resultText,
      mode,
      setGoal: opts?.setGoal,
      llm,
    })
    if (!thread) return
    deps.setThreads((current) =>
      current.map((item) =>
        item.id === threadId
          ? thread
          : item
      )
    )
  }

  const onRecord = createWorkspaceRecordHandler({
    activityRef,
    currentTaskRef,
    lastRunModeRef,
    ingestRecord: liveSessionRef.current.ingest,
    persistThreadMemory,
    setStatus,
    setStatusDetail,
    setLiveFeed,
    setTokenUsage,
    setTopVideos,
    setResultsMarked,
    setResultsStale,
    setListWarnings,
    setPageSignalsPreview,
    setAwaitingQuestion,
    setRunOutcome,
    setRunning,
    setRunStartedAt,
    setTraceOpen,
    runningRef,
  })

  const runLifecycle = createRunLifecycle({
    pageAskBusy: deps.pageAskBusy,
    running,
    paused,
    awaitingQuestion,
    targetTab: deps.targetTab,
    pageAskAbortRef: deps.pageAskAbortRef,
    tabRef,
    pauseRef,
    queueRef,
    runningRef,
    currentTaskRef,
    voiceRef: deps.voiceRef,
    explainAfterPickRef: deps.explainAfterPickRef,
    workspaceRef,
    workspaceTabRef,
    workspaceGenerationRef,
    resumeLockRef,
    loadedThreadRef,
    setPageAskBusy: deps.setPageAskBusy,
    setStatus,
    setStatusDetail,
    setLiveFeed,
    setRunOutcome,
    setQueuePending,
    setCurrentTask,
    setPaused,
    setRunning,
    setRunStartedAt,
    setThreads: deps.setThreads,
    setActiveThreadId: deps.setActiveThreadId,
    setTask: deps.setTask,
    setVoiceAttachment: deps.setVoiceAttachment,
    setImageAttachment: deps.setImageAttachment,
    setRecords,
    setTopVideos,
    setResultsMarked,
    setResultsStale,
    setListWarnings,
    setTokenUsage,
    setAwaitingQuestion,
    setBlockedQuestions,
    setPickedElement: deps.setPickedElement,
    setPickingElement: deps.setPickingElement,
    setQueuedExplain: deps.setQueuedExplain,
    setReadinessItems,
    setTraceOpen,
    push,
    bindLiveSession: (sessionId) => liveSessionRef.current.bindSession(sessionId),
    syncPendingTasks: queueControl.syncPendingTasks,
    persistWorkspace: restore.persistWorkspace,
    agentRun,
  })

  useEffect(() => {
    runningRef.current = running
  }, [running])

  useEffect(() => () => liveSessionRef.current.dispose(), [])

  useTargetTabSync(tabRef, runningRef, deps.setTargetTab)

  useWorkspaceRestoreEffects({
    workspaceRef,
    workspaceTabRef,
    workspaceGenerationRef,
    resumeLockRef,
    runningRef,
    tabRef,
    loadedThreadRef,
    sessionRef,
    currentTaskRef,
    pendingTasksRef,
    getSession,
    adoptTab: tabControl.adoptTab,
    syncPendingTasks: queueControl.syncPendingTasks,
    setThreads: deps.setThreads,
    setActiveThreadId: deps.setActiveThreadId,
    setTask: deps.setTask,
    setRecords,
    setTraceOpen,
    setStatus,
    setTargetTab: deps.setTargetTab,
    setCurrentTask,
    listThreads,
    listThreadRecords,
    bindLiveSession: (sessionId) => liveSessionRef.current.bindSession(sessionId),
    ...restore,
  })

  useEffect(() => {
    const onMessage = (message: { type?: string }): void => {
      if (message.type === 'NAVIFORGE_MARK_STALE') setResultsStale(true)
    }
    chrome.runtime.onMessage.addListener(onMessage)
    return () => chrome.runtime.onMessage.removeListener(onMessage)
  }, [])

  useEffect(() => {
    if (!deps.activeThreadId || runningRef.current) return
    if (loadedThreadRef.current === deps.activeThreadId) return
    loadedThreadRef.current = deps.activeThreadId
    void listThreadRecords(deps.activeThreadId).then((threadRecords) => {
      if (!threadRecords.length || runningRef.current) return
      setRecords(threadRecords)
    })
  }, [deps.activeThreadId])

  useEffect(() => {
    workspaceRef.current = {
      task: deps.task,
      activeThreadId: deps.activeThreadId,
      traceOpen,
      targetTab: deps.targetTab,
    }
  }, [deps.activeThreadId, deps.targetTab, deps.task, traceOpen])

  useWorkspaceAgentSync({
    tabRef,
    explainAfterPickRef: deps.explainAfterPickRef,
    onRecord,
    onRunFinished: queueControl.finishBackgroundRun,
    syncPendingTasks: queueControl.syncPendingTasks,
    push,
    setPickingElement: deps.setPickingElement,
    setPickedElement: deps.setPickedElement,
    setQueuedExplain: deps.setQueuedExplain,
    setTask: deps.setTask,
    setRunning,
    setRunStartedAt,
    setStatus,
    setQueuePending,
    setTargetTab: deps.setTargetTab,
  })

  return {
    records,
    setRecords,
    status,
    setStatus,
    statusDetail,
    setStatusDetail,
    liveFeed,
    setLiveFeed,
    setRunOutcome,
    setTokenUsage,
    running,
    runStartedAt,
    paused,
    awaitingQuestion,
    blockedQuestions,
    lastRunFailed,
    queuePending,
    pendingTasks,
    currentTask,
    runOutcome,
    topVideos,
    resultsMarked,
    resultsStale,
    listWarnings,
    pageSignalsPreview,
    tokenUsage,
    readinessItems,
    traceOpen,
    enabledSkills,
    llm,
    push,
    appendLocal: liveSessionRef.current.appendLocal,
    runningRef,
    bindActiveTab: tabControl.bindActiveTab,
    adoptTab: tabControl.adoptTab,
    pickElement: tabControl.pickElement,
    clearPickedElement: tabControl.clearPickedElement,
    openTabPicker: tabControl.openTabPicker,
    switchToTab: tabControl.switchToTab,
    focusMarkedVideo: tabControl.focusMarkedVideo,
    replacePendingTasks: queueControl.replacePendingTasks,
    refreshPendingTasks: queueControl.refreshPendingTasks,
    enqueueTask: queueControl.enqueueTask,
    enqueueSteer: queueControl.enqueueSteer,
    replyHitl: queueControl.replyHitl,
    stop: runLifecycle.stop,
    togglePause: runLifecycle.togglePause,
    startNewThread: runLifecycle.startNewThread,
    resumeSession: restore.applyResumeSession,
  }
}
