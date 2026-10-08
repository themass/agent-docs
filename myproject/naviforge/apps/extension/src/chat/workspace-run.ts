import type { MutableRefObject } from 'react'
import { RUN_STATUS, type WorkspaceRunStatus } from '../lib/run-phase'
import {
  createHitlGate,
  createMessageQueue,
  createPauseController,
  type LlmConfig,
  type QueuedTask,
  shouldEnableNetworkPlane,
} from '@naviforge/runtime'
import { formatSkillGuidance, routeSkills, type Skill } from '@naviforge/skill-runtime'
import { capabilityGatesFromPrivacy } from '@naviforge/shared'

import { addActivity } from '../lib/activity-store'
import { createHostMcpRuntime } from '../lib/host-bridge'
import { getActiveModelProfile, loadModelProfiles, profileToLlmConfig } from '../lib/llm-profiles'
import { hasBroadHostAccess, requestBroadHostAccess } from '../lib/host-permissions'
import { loadNewApiAuth } from '../lib/newapi-auth'
import { isManagedLoginEnabled } from '../lib/managed-login-feature'
import { syncManagedProfilesFromNewApi } from '../lib/newapi-sync'
import { blockingReadinessItems, runReadinessChecks, type RunReadinessItem } from '../lib/run-readiness'
import {
  continueSession,
  createSession,
  createThread,
  getLatestThreadSession,
  getSession,
  listThreads,
  updateThreadTitle,
} from '../lib/session-store'
import { buildThreadContext, isContinuationMessage, sessionDisplayTitle, type AgentThread } from '../lib/thread-model'
import { isBrowserPdfUrl, ocrVisiblePage } from '../lib/vision-ocr'
import { STORAGE } from '../lib/settings'
import { safeRuntimeSendMessage } from '../lib/extension-runtime'
import type { TraceRecord } from '@naviforge/session'
import type { WorkspaceRunOutcome } from './run-outcome'

export type AgentStarterDeps = {
  llm: LlmConfig
  enabledSkills: Skill[]
  enforceSkillToolAllowlist: boolean
  useNetwork: boolean
  captureNetworkBodies: boolean
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  visionEnabled: boolean
  maxAgentSteps: number
  sameFailureLimit: number
  runTimeoutMs: number
  tokenBudget: number
  maxInputTokens: number
  hitlPolicy: 'strict' | 'balanced' | 'permissive'
  rollbackUrlDrift: boolean
  threads: AgentThread[]
  activeThreadId: string
  workspaceGenerationRef: MutableRefObject<number>
  resumeLockRef: MutableRefObject<boolean>
  abortRef: MutableRefObject<AbortController | null>
  pauseRef: MutableRefObject<ReturnType<typeof createPauseController>>
  queueRef: MutableRefObject<ReturnType<typeof createMessageQueue>>
  hitlRef: MutableRefObject<ReturnType<typeof createHitlGate>>
  pendingTasksRef: MutableRefObject<QueuedTask[]>
  pendingVoiceByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; path?: string; label: string }>
  >
  pendingImageByTaskRef: MutableRefObject<
    Map<string, { dataUrl: string; label: string }>
  >
  runningRef: MutableRefObject<boolean>
  currentTaskRef: MutableRefObject<QueuedTask | null>
  sessionRef: MutableRefObject<string | null>
  activityRef: MutableRefObject<string | null>
  activeRunIdRef: MutableRefObject<string | null>
  loadedThreadRef: MutableRefObject<string>
  setReadinessItems(value: RunReadinessItem[]): void
  setQueuePending(value: { steering: number; followUp: number }): void
  setAwaitingQuestion(value: string | null): void
  setBlockedQuestions(value: string[]): void
  setLastRunFailed(value: boolean): void
  setRunOutcome(value: WorkspaceRunOutcome | null): void
  setTopVideos(value: import('./workspace-helpers').TopVideo[]): void
  setResultsMarked(value: boolean): void
  setResultsStale(value: boolean): void
  setListWarnings(value: { missed?: string[]; offscreen?: string[]; shortfall?: string }): void
  setTokenUsage(value: {
    lastPrompt: number
    lastCompletion: number
    runTotal: number
  } | null): void
  setTraceOpen(value: boolean): void
  setPrivacyToast(value: string | null): void
  setPaused(value: boolean): void
  setRunning(value: boolean): void
  setRunStartedAt(value: number | null): void
  setCurrentTask(value: QueuedTask | null): void
  setTask(value: string): void
  setStatus(value: WorkspaceRunStatus): void
  setLiveFeed(value: string[]): void
  setThreads(updater: (current: AgentThread[]) => AgentThread[]): void
  setActiveThreadId(value: string): void
  push(line: string): void
  bindLiveSession(sessionId: string | null): Promise<void>
  appendLocal(
    type: 'user.task',
    payload: {
      text: string
      audioPath?: string
      audioLabel?: string
      audioDataUrl?: string
      imageDataUrl?: string
      imageLabel?: string
    },
    trace?: { taskId?: string; turn?: number }
  ): void
  recordSession(record: {
    type: 'run.note'
    payload: { topic: string; text: string }
  }): void
  syncPendingTasks(tasks: QueuedTask[]): void
  abortUnstarted(taskItem: QueuedTask, title: string, message: string, optionsSection?: string): void
  bindActiveTab(): Promise<chrome.tabs.Tab | null>
  listThreadRecords(threadId: string): Promise<import('@naviforge/session').TraceRecord[]>
}

export function createAgentStarter(deps: AgentStarterDeps) {
  async function resolveRunLlm(): Promise<LlmConfig> {
    const auth = await loadNewApiAuth()
    const managedFeature = await isManagedLoginEnabled()
    if (managedFeature && auth.mode === 'managed') {
      const profilesBefore = await loadModelProfiles()
      const activeBefore = getActiveModelProfile(profilesBefore)
      const staleHttps = /^https:\/\/gpt\.sspacee\.com/i.test(activeBefore.baseURL)
      await syncManagedProfilesFromNewApi({ force: staleHttps })
      const profiles = await loadModelProfiles()
      return profileToLlmConfig(getActiveModelProfile(profiles))
    }
    return deps.llm
  }

  async function startRun(taskItem: QueuedTask): Promise<void> {
    deps.workspaceGenerationRef.current += 1
    deps.resumeLockRef.current = false
    const llm = await resolveRunLlm()
    if (!llm.apiKey.trim()) {
      const auth = await loadNewApiAuth()
      const managedFeature = await isManagedLoginEnabled()
      const hint =
        managedFeature && auth.mode === 'managed'
          ? '请先登录 NewAPI 托管（设置 → 高级 → 启用托管登录）'
          : 'Settings → Models'
      deps.push(`✗ 请先在设置中配置模型 API Key（${hint}）`)
      deps.setReadinessItems([
        {
          id: 'api_key',
          ok: false,
          label: '模型 API Key',
          detail: hint,
          blocking: true,
        },
      ])
      deps.abortUnstarted(taskItem, '未配置模型', '请先在设置中填写 API Key', 'settings')
      return
    }
    const tab = await deps.bindActiveTab()
    if (!tab?.id) {
      deps.abortUnstarted(taskItem, '无法绑定标签', '请先打开一个普通网页标签，或点顶栏切换')
      return
    }
    if (!(await hasBroadHostAccess())) {
      const granted = await requestBroadHostAccess()
      if (!granted) {
        deps.push('✗ 需要「访问网站」权限才能操作页面')
        deps.abortUnstarted(taskItem, '缺少网站权限', '请在 Chrome 弹窗中允许，或到扩展详情 → 站点访问')
        return
      }
    }
    deps.abortRef.current?.abort()
    deps.abortRef.current = new AbortController()
    deps.pauseRef.current = createPauseController()
    deps.queueRef.current = createMessageQueue()
    // Merge anything enqueued while we were awaiting tab/bind.
    const followUpQueue = deps.pendingTasksRef.current.filter((task) => task.id !== taskItem.id)
    if (followUpQueue.length) deps.queueRef.current.setFollowUps(followUpQueue)
    deps.hitlRef.current = createHitlGate()
    deps.setQueuePending({ steering: 0, followUp: 0 })
    deps.setAwaitingQuestion(null)
    deps.setBlockedQuestions([])
    deps.setLastRunFailed(false)
    deps.setRunOutcome(null)
    deps.setTopVideos([])
    deps.setResultsMarked(false)
    deps.setResultsStale(false)
    deps.setListWarnings({})
    deps.setTokenUsage(null)
    deps.setLiveFeed([])
    deps.setTraceOpen(false)
    deps.setPrivacyToast(null)
    deps.setReadinessItems([])
    deps.setPaused(false)
    deps.runningRef.current = true
    deps.setRunning(true)
    deps.setRunStartedAt(Date.now())
    deps.setCurrentTask(taskItem)
    deps.currentTaskRef.current = taskItem
    const taskText = taskItem.text
    deps.setTask('')
    deps.push(taskText)
    deps.setStatus(RUN_STATUS.PREPARING)

    // Soft hints only — never host-route a single skill or dump bodies into the prompt.
    const suggested = routeSkills(taskText, deps.enabledSkills, 3)
    const skillGuidance = deps.enabledSkills.length
      ? formatSkillGuidance(deps.enabledSkills, { hints: suggested })
      : undefined
    const skillRegistry = deps.enabledSkills.map((skill) => ({
      id: skill.manifest.id,
      version: skill.manifest.version,
      description: skill.manifest.description,
      instructions: skill.instructions,
      tools: skill.manifest.permissions?.tools,
      files: skill.files,
    }))
    const SAFE_BASE_TOOLS = [
      'browser_observe',
      'browser_act',
      'skill_load',
      'system_done',
      'system_ask_user',
      'system_captcha_wait',
    ] as const
    const permissionSources = suggested.length
      ? suggested
      : [{ manifest: { permissions: { tools: [...SAFE_BASE_TOOLS] } } } as Skill]
    const allowedTools = deps.enforceSkillToolAllowlist
      ? [
          ...new Set(
            permissionSources.flatMap(
              (skill) => skill.manifest.permissions?.tools ?? [...SAFE_BASE_TOOLS]
            )
          ),
        ]
      : undefined
    let thread = deps.threads.find((item) => item.id === deps.activeThreadId)
    if (!thread) {
      thread = await createThread(taskText)
      deps.setThreads((current) => [thread!, ...current].slice(0, 50))
      deps.loadedThreadRef.current = thread.id
      deps.setActiveThreadId(thread.id)
    }
    const threadRecords = await deps.listThreadRecords(thread.id)
    const displayTitle = sessionDisplayTitle(taskText, threadRecords)
    if (
      !isContinuationMessage(taskText) &&
      (thread.title === '新会话' || thread.title === 'Untitled thread')
    ) {
      const shortTitle = displayTitle.replace(/\s+/g, ' ').trim().slice(0, 40)
      await updateThreadTitle(thread.id, shortTitle)
      thread = { ...thread, title: shortTitle }
      deps.setThreads((current) => current.map((item) => (item.id === thread!.id ? thread! : item)))
    }
    let threadContext = buildThreadContext(thread, threadRecords)
    if (isBrowserPdfUrl(tab.url)) {
      try {
        deps.push('PDF 页：自动 OCR 可见区域…')
        const ocr = await ocrVisiblePage(tab)
        if (ocr.text.trim()) {
          threadContext = {
            ...threadContext,
            conversation: [
              threadContext.conversation,
              'PAGE TEXT (OCR from visible PDF page — Chrome PDF viewer has no readable DOM):',
              ocr.text.slice(0, 12_000),
            ].join('\n\n'),
          }
          deps.push(`PDF OCR：${ocr.text.length} 字`)
        }
      } catch (error) {
        deps.push(`PDF OCR 跳过：${(error as Error).message}`)
      }
    }
    const page = { tabId: tab.id, url: tab.url, title: tab.title }
    const refSession = deps.sessionRef.current ? await getSession(deps.sessionRef.current) : undefined
    const latestSession = await getLatestThreadSession(thread.id)
    const prior =
      refSession?.threadId === thread.id
        ? refSession
        : latestSession?.threadId === thread.id
          ? latestSession
          : undefined
    const voice = deps.pendingVoiceByTaskRef.current.get(taskItem.id)
    deps.pendingVoiceByTaskRef.current.delete(taskItem.id)
    const image = deps.pendingImageByTaskRef.current.get(taskItem.id)
    deps.pendingImageByTaskRef.current.delete(taskItem.id)
    const extras = voice?.path ? { audioPath: voice.path, audioLabel: voice.label } : undefined
    const runId = crypto.randomUUID()
    deps.activeRunIdRef.current = runId
    if (prior) {
      await continueSession(prior.id, taskText, page, extras)
      deps.sessionRef.current = prior.id
    } else {
      const session = await createSession(taskText, thread.id, page, extras)
      deps.sessionRef.current = session.id
    }
    const sessionAnchor = prior?.task ?? taskText
    const networkForTask = deps.useNetwork || shouldEnableNetworkPlane(taskText, sessionAnchor)

    const readiness = await runReadinessChecks({
      tabId: tab.id,
      tabUrl: tab.url,
      tabTitle: tab.title,
      apiKey: llm.apiKey,
      useNetwork: networkForTask,
      skillLabel: suggested[0]?.manifest.id,
      enforceSkillAllowlist: deps.enforceSkillToolAllowlist,
    })
    deps.setReadinessItems(readiness)
    const blockers = blockingReadinessItems(readiness)
    if (blockers.length) {
      deps.abortUnstarted(
        taskItem,
        '启动检查未通过',
        blockers.map((item) => `${item.label}: ${item.detail}`).join('\n')
      )
      deps.setTraceOpen(true)
      return
    }

    if (tab.url && !/localhost:4177|127\.0\.0\.1:4177/.test(tab.url) && /测试页|Success|Go/.test(taskText)) {
      deps.push('提示: 任务像是测 test-site，但当前活动标签不是 localhost:4177 — 请先打开测试页再 Run')
    }

    const mcp = await createHostMcpRuntime()
    if (!mcp.ok) deps.push(`MCP: ${mcp.reason}`)
    else if (mcp.mcpTools.length) deps.push(`mcp: ${mcp.mcpTools.length} allowlisted tools`)

    await deps.bindLiveSession(deps.sessionRef.current)
    if (voice) {
      deps.appendLocal(
        'user.task',
        {
          text: taskText,
          audioPath: voice.path,
          audioLabel: voice.label,
          audioDataUrl: voice.dataUrl,
        },
        { taskId: taskItem.id }
      )
    }
    if (mcp.ok && mcp.mcpTools.length) {
      deps.recordSession({
        type: 'run.note',
        payload: {
          topic: 'mcp',
          text: mcp.mcpTools.map((tool) => `${tool.serverName}.${tool.name}`).join('\n'),
        },
      })
    }
    const activity = await addActivity({
      kind: 'agent',
      status: 'running',
      title: displayTitle.slice(0, 80) || 'Agent task',
    })
    deps.activityRef.current = activity.id

    // Final merge: anything enqueued during preflight/MCP setup.
    const latestFollowUps = deps.pendingTasksRef.current.filter((task) => task.id !== taskItem.id)
    deps.syncPendingTasks(latestFollowUps)
    deps.queueRef.current.setFollowUps(latestFollowUps)

    if (networkForTask && !deps.useNetwork) {
      deps.recordSession({
        type: 'run.note',
        payload: {
          topic: 'internal',
          text: 'PREFLIGHT: auto-enabled network plane for in_page media/script/data task (privacy override for this run).',
        },
      })
    }
    const gates = capabilityGatesFromPrivacy({
      networkEnabled: networkForTask,
      captureNetworkBodies: deps.captureNetworkBodies,
      allowDomInject: deps.allowDomInject,
      allowNetworkIntercept: deps.allowNetworkIntercept,
      visionEnabled: deps.visionEnabled,
    })
    const started = (await safeRuntimeSendMessage({
      type: 'AGENT_RUN',
      action: 'start',
      request: {
        id: runId,
        sessionId: deps.sessionRef.current!,
        task: taskText,
        taskAnchor: sessionAnchor,
        taskId: taskItem.id,
        followUpQueue: latestFollowUps,
        tabId: tab.id,
        llm,
        skills: deps.enabledSkills.map((skill) => skill.manifest.id),
        skillRegistry,
        skillGuidance,
        threadContext,
        allowedTools: allowedTools?.length ? allowedTools : undefined,
        ...gates,
        maxSteps: deps.maxAgentSteps,
        sameFailureLimit: deps.sameFailureLimit,
        runTimeoutMs: deps.runTimeoutMs,
        runTokenBudget: deps.tokenBudget,
        maxInputTokens: deps.maxInputTokens,
        hitlPolicy: deps.hitlPolicy,
        rollbackUrlDrift: deps.rollbackUrlDrift,
        ...(image ? { imageDataUrl: image.dataUrl, imageLabel: image.label } : {}),
      },
    })) as { ok?: boolean; error?: string } | undefined
    if (!started?.ok) {
      throw new Error(started?.error ?? 'failed to start background run')
    }
    deps.setStatus(RUN_STATUS.PREPARING)
  }

  return { startRun }
}

export type RunLifecycleDeps = {
  pageAskBusy: boolean
  running: boolean
  paused: boolean
  awaitingQuestion: string | null
  targetTab: { id: number; url?: string; title?: string; windowId?: number } | null
  pageAskAbortRef: MutableRefObject<AbortController | null>
  tabRef: MutableRefObject<number | null>
  pauseRef: MutableRefObject<ReturnType<typeof createPauseController>>
  queueRef: MutableRefObject<ReturnType<typeof createMessageQueue>>
  runningRef: MutableRefObject<boolean>
  currentTaskRef: MutableRefObject<QueuedTask | null>
  voiceRef: MutableRefObject<{ dataUrl: string; path?: string; label: string } | null>
  explainAfterPickRef: MutableRefObject<boolean>
  workspaceRef: MutableRefObject<import('../lib/tab-workspace').TabWorkspace>
  workspaceTabRef: MutableRefObject<number | null>
  workspaceGenerationRef: MutableRefObject<number>
  resumeLockRef: MutableRefObject<boolean>
  loadedThreadRef: MutableRefObject<string>
  setPageAskBusy(value: boolean): void
  setStatus(value: WorkspaceRunStatus): void
  setStatusDetail(value: string | null): void
  setLiveFeed(value: string[]): void
  setRunOutcome(value: WorkspaceRunOutcome | null): void
  setQueuePending(value: { steering: number; followUp: number }): void
  setCurrentTask(value: QueuedTask | null): void
  setPaused(value: boolean): void
  setRunning(value: boolean): void
  setRunStartedAt(value: number | null): void
  setThreads(value: import('../lib/thread-model').AgentThread[]): void
  setActiveThreadId(value: string): void
  setTask(value: string): void
  setVoiceAttachment(value: { dataUrl: string; path?: string; label: string } | null): void
  setImageAttachment(value: { dataUrl: string; label: string } | null): void
  setRecords(value: TraceRecord[]): void
  setTopVideos(value: import('./workspace-helpers').TopVideo[]): void
  setResultsMarked(value: boolean): void
  setResultsStale(value: boolean): void
  setListWarnings(value: { missed?: string[]; offscreen?: string[]; shortfall?: string }): void
  setTokenUsage(value: {
    lastPrompt: number
    lastCompletion: number
    runTotal: number
  } | null): void
  setAwaitingQuestion(value: string | null): void
  setBlockedQuestions(value: string[]): void
  setPickedElement(value: import('./workspace-helpers').PickedElement | null): void
  setPickingElement(value: boolean): void
  setQueuedExplain(value: import('./workspace-helpers').PickedElement | null): void
  setReadinessItems(value: RunReadinessItem[]): void
  setTraceOpen(value: boolean): void
  push(line: string): void
  bindLiveSession(sessionId: string | null): Promise<void>
  syncPendingTasks(tasks: QueuedTask[]): void
  persistWorkspace(tabId: number): Promise<void>
  agentRun: {
    stop(): Promise<unknown>
    pause(): Promise<unknown>
    resume(): Promise<unknown>
  }
}

export function createRunLifecycle(deps: RunLifecycleDeps) {
  function togglePause(): void {
    if (!deps.running || deps.awaitingQuestion) return
    if (deps.paused) {
      void deps.agentRun.resume()
      deps.setPaused(false)
    } else {
      void deps.agentRun.pause()
      deps.setPaused(true)
    }
  }

  function stop(): void {
    if (deps.pageAskBusy) {
      deps.pageAskAbortRef.current?.abort()
      deps.pageAskAbortRef.current = null
      deps.setPageAskBusy(false)
      deps.setStatus(RUN_STATUS.CANCELLED)
      deps.setRunOutcome({ kind: 'cancelled', title: '已停止', message: '页面问答已取消' })
      return
    }
    void deps.agentRun.stop()
    if (deps.tabRef.current != null) {
      void safeRuntimeSendMessage({
        type: 'NETWORK',
        action: 'cancelWaits',
        tabId: deps.tabRef.current,
      })
    }
    deps.pauseRef.current.resume()
    deps.queueRef.current.clear()
    deps.setQueuePending({ steering: 0, followUp: 0 })
    deps.setCurrentTask(null)
    deps.currentTaskRef.current = null
    deps.setPaused(false)
    deps.runningRef.current = false
    deps.setRunning(false)
    deps.setRunStartedAt(null)
    deps.setAwaitingQuestion(null)
    deps.setStatus(RUN_STATUS.CANCELLED)
    deps.setStatusDetail(null)
    deps.setLiveFeed([])
    deps.setRunOutcome({ kind: 'cancelled', title: '已停止', message: 'Agent 运行已取消' })
    deps.push('✓ stopped')
  }

  async function startNewThread(): Promise<void> {
    deps.workspaceGenerationRef.current += 1
    deps.resumeLockRef.current = false
    if (deps.runningRef.current) stop()

    const thread = await createThread('新会话')
    deps.setThreads(await listThreads())
    deps.loadedThreadRef.current = thread.id
    deps.setActiveThreadId(thread.id)
    deps.setTask('')
    deps.voiceRef.current = null
    deps.setVoiceAttachment(null)
    deps.setImageAttachment(null)
    deps.setRecords([])
    deps.setRunOutcome(null)
    deps.setTopVideos([])
    deps.setResultsMarked(false)
    deps.setResultsStale(false)
    deps.setListWarnings({})
    deps.setTokenUsage(null)
    deps.setAwaitingQuestion(null)
    deps.setBlockedQuestions([])
    deps.setStatus(RUN_STATUS.IDLE)
    deps.setRunStartedAt(null)
    deps.setPickedElement(null)
    deps.setPickingElement(false)
    deps.explainAfterPickRef.current = false
    deps.setQueuedExplain(null)
    deps.setQueuePending({ steering: 0, followUp: 0 })
    deps.syncPendingTasks([])
    deps.setCurrentTask(null)
    deps.currentTaskRef.current = null
    deps.setReadinessItems([])
    deps.setTraceOpen(false)
    await chrome.storage.local.remove([STORAGE.resumeSession, STORAGE.activeRun])
    await deps.bindLiveSession(null)
    deps.workspaceRef.current = {
      task: '',
      activeThreadId: thread.id,
      traceOpen: false,
      targetTab: deps.targetTab,
    }
    if (deps.workspaceTabRef.current != null) await deps.persistWorkspace(deps.workspaceTabRef.current)
  }

  return { togglePause, stop, startNewThread }
}
