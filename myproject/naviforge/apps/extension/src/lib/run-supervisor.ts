import type { QueuedTask } from '@naviforge/runtime'
import { createTraceRecord, type TraceRecord, type TraceRecordPayload, type TraceRecordType } from '@naviforge/session'
import {
  AGENT_TOOL_IDS,
  applyAgentCapabilityGates,
  mcpQualifiedName,
} from '@naviforge/shared'

import { loadResolvedLocale } from '../i18n'
import {
  colorForAgentTask,
  formatAgentGroupTitle,
  type AgentPresence,
} from './agent-presence'
import { pinAgentTabGroup } from './agent-tab-group'
import { createChromeDomPlane } from './chrome-dom-plane'
import { createChromeNetworkPlane } from './chrome-network-plane'
import { attachNetwork, detachNetwork } from './network-recorder'
import {
  attachNetworkWithRecovery,
  formatNetworkDegradedNote,
} from './network-attach-recovery'
import { createChromeRecipePlane } from './chrome-recipe-plane'
import { createChromeScriptPlane } from './chrome-script-plane'
import { createChromeTabsPlane, createEphemeralTabScope } from './chrome-tabs-plane'
import { createHostMcpRuntime } from './host-bridge'
import { createChromeWorkspacePlane } from './local-workspace'
import {
  appendSessionRecord,
  completeLeafSession,
  completeSession,
  createLeafSession,
  getSession,
  updateSessionPage,
} from './session-store'
import type { LlmConfig } from '@naviforge/runtime'
import type { Skill } from '@naviforge/skill-runtime'
import { DEFAULT_PRIVACY, STORAGE } from './settings'
import { buildHostPollRunRequest } from './host-run-request'
import { leafProgressLine } from './leaf-feed'
import { createWebSearchPlane } from './web-search'
import { createFetchTextPlane } from './fetch-text'
import { forgePlaybookAfterSuccessfulRun } from './playbook-forge-after-run'
import { learnSiteRecipeFromRun } from './recipe-from-run'

import {
  composeSystemPrompt,
  createHitlGate,
  createMessageQueue,
  createPauseController,
  resolveTaskMode,
  resolveTaskIntent,
  resolveDeliverable,
  runAgent,
  type RunAgentResult,
  workspaceSlug,
} from '@naviforge/runtime'
import { type BackgroundRunRequest, isValidBackgroundRunRequest } from './run-supervisor-request'
export type { BackgroundRunRequest } from './run-supervisor-request'
export { isValidBackgroundRunRequest } from './run-supervisor-request'

type ActiveRun = {
  request: BackgroundRunRequest
  tabId: number
  status: string
  events: TraceRecord[]
  abort: AbortController
  pause: ReturnType<typeof createPauseController>
  queue: ReturnType<typeof createMessageQueue>
  hitl: ReturnType<typeof createHitlGate>
  sessionWrite: Promise<void>
  groupId?: number
  lastAction?: string
  /** childRunId → leaf session id */
  leafSessions: Map<string, string>
}

export type AgentRunSummary =
  | { active: false }
  | {
      active: true
      id: string
      task: string
      tabId: number
      status: string
      events: TraceRecord[]
      tasks: QueuedTask[]
      pending: { steering: number; followUp: number }
    }

export class RunSupervisor {
  private activeRun: ActiveRun | null = null
  private presenceBeat: ReturnType<typeof setInterval> | undefined

  summary(): AgentRunSummary {
    if (!this.activeRun) return { active: false }
    const run = this.activeRun
    return {
      active: true,
      id: run.request.id,
      task: run.request.task,
      tabId: run.tabId,
      status: run.status,
      events: run.events,
      tasks: run.queue.listFollowUps(),
      pending: run.queue.pending(),
    }
  }

  hasActiveRun(): boolean {
    return this.activeRun !== null
  }

  /**
   * Keep the active run's tabId in sync when something outside the main
   * run loop retargets the tab — e.g. NETWORK attach recovery duplicating
   * the tab to escape a foreign/DevTools debugger. No-op if there is no
   * active run or the run has already moved off `fromTabId` (stale call).
   */
  retargetActiveRunTab(fromTabId: number, toTabId: number): void {
    const run = this.activeRun
    if (!run || run.tabId !== fromTabId || toTabId === fromTabId) return
    run.tabId = toTabId
    this.writePresence(this.presenceFromRun(run))
    void this.bindRunTabGroup(run)
  }

  dispatch(message: { action?: string; request?: unknown; text?: string; id?: string; tasks?: unknown }): {
    ok: boolean
    error?: string
    async?: boolean
    response?: Record<string, unknown>
  } {
    switch (message.action) {
      case 'status':
        if (this.activeRun) {
          return { ok: true, response: { ok: true, ...this.summary() } }
        }
        return { ok: true, async: true }
      case 'start': {
        if (!isValidBackgroundRunRequest(message.request)) {
          return { ok: false, error: 'invalid run request' }
        }
        const gates = applyAgentCapabilityGates(message.request, message.request)
        void this.start({ ...message.request, ...gates })
        return { ok: true, response: { ok: true, id: message.request.id } }
      }
      case 'stop': {
        const run = this.activeRun
        if (run) {
          run.hitl.cancelWaiting()
          run.abort.abort()
          this.publishBackgroundRecord('run.error', { message: 'Stopped by user', code: 'cancelled' })
          if (run.request.sessionId) {
            void completeSession(run.request.sessionId, 'cancelled', 'Stopped by user')
          }
          this.activeRun = null
          this.stopPresenceBeat()
          this.writePresence(null)
          this.persistRun()
        }
        return { ok: true, response: { ok: true } }
      }
      case 'pause':
        this.activeRun?.pause.pause()
        if (this.activeRun) {
          this.activeRun.status = 'PAUSED'
          this.writePresence(this.presenceFromRun(this.activeRun, { waiting: true }))
        }
        return { ok: true, response: { ok: Boolean(this.activeRun) } }
      case 'resume':
        this.activeRun?.pause.resume()
        if (this.activeRun) {
          this.activeRun.status = 'RUNNING'
          this.writePresence(this.presenceFromRun(this.activeRun, { waiting: false }))
        }
        return { ok: true, response: { ok: Boolean(this.activeRun) } }
      case 'steer':
        if (!this.activeRun || typeof message.text !== 'string') {
          return { ok: false, error: 'no active run' }
        }
        if (this.activeRun.hitl.isWaiting()) {
          const ok = this.activeRun.hitl.reply(message.text)
          return {
            ok,
            response: { ok, asHitl: true, pending: this.activeRun.queue.pending() },
          }
        }
        this.activeRun.queue.steer(message.text)
        return { ok: true, response: { ok: true, pending: this.activeRun.queue.pending() } }
      case 'follow_up':
        if (!this.activeRun || typeof message.text !== 'string') {
          return { ok: false, error: 'no active run' }
        }
        this.activeRun.queue.followUp(message.text, typeof message.id === 'string' ? message.id : undefined)
        return {
          ok: true,
          response: {
            ok: true,
            pending: this.activeRun.queue.pending(),
            tasks: this.activeRun.queue.listFollowUps(),
            followUps: this.activeRun.queue.listFollowUps().map((task) => task.text),
          },
        }
      case 'queue_list':
        return {
          ok: true,
          response: {
            ok: Boolean(this.activeRun),
            tasks: this.activeRun?.queue.listFollowUps() ?? [],
            pending: this.activeRun?.queue.pending() ?? { steering: 0, followUp: 0 },
          },
        }
      case 'queue_set': {
        if (!this.activeRun || !Array.isArray(message.tasks)) {
          return { ok: false, error: 'no active run' }
        }
        this.activeRun.queue.setFollowUps(
          message.tasks
            .filter(
              (task: { id?: string; text?: string }): task is { id: string; text: string } =>
                typeof task.id === 'string' &&
                task.id.length > 0 &&
                typeof task.text === 'string' &&
                task.text.trim().length > 0
            )
            .map((task: { id: string; text: string }) => ({
              id: task.id,
              text: task.text.trim(),
            }))
        )
        return {
          ok: true,
          response: {
            ok: true,
            tasks: this.activeRun.queue.listFollowUps(),
            pending: this.activeRun.queue.pending(),
          },
        }
      }
      case 'reply':
        return {
          ok: true,
          response: { ok: this.activeRun?.hitl.reply(String(message.text ?? '')) === true },
        }
      default:
        return { ok: false, error: 'unknown AGENT_RUN action' }
    }
  }

  async start(request: BackgroundRunRequest): Promise<RunAgentResult | undefined> {
    if (this.activeRun) this.activeRun.abort.abort()
    const abort = new AbortController()
    const pause = createPauseController()
    const queue = createMessageQueue()
    if (request.followUpQueue?.length) {
      queue.setFollowUps(request.followUpQueue)
    }
    const hitl = createHitlGate()
    this.activeRun = {
      request,
      tabId: request.tabId,
      status: 'PREPARING',
      events: [],
      abort,
      pause,
      queue,
      hitl,
      sessionWrite: Promise.resolve(),
      leafSessions: new Map(),
    }
    this.persistRun()
    this.startPresenceBeat(this.activeRun)
    void this.bindRunTabGroup(this.activeRun)
    const run = this.activeRun
    const mcp = await createHostMcpRuntime()
    const mcpNames = mcp.ok ? mcp.mcpTools.map((tool) => mcpQualifiedName(tool.serverId, tool.name)) : []
    if (!mcp.ok) {
      this.publishBackgroundRecord('run.log', { message: `MCP: ${mcp.reason}` })
    } else {
      this.publishBackgroundRecord('run.log', {
        message: `MCP: ${mcp.mcpTools.length} tools as mcp__* (${mcpNames.slice(0, 5).join(', ')}${mcpNames.length > 5 ? '…' : ''})`,
      })
    }
    this.publishBackgroundRecord('run.context', {
      systemPrompt: composeSystemPrompt(request.skillGuidance, { hasMcpTools: mcpNames.length > 0 }),
      taskMode: resolveTaskMode(request.task),
      tools: [...AGENT_TOOL_IDS, ...mcpNames],
      skills: request.skills,
      skillGuidance: request.skillGuidance,
      mcpTools: mcp.ok
        ? mcp.mcpTools.map((tool) => ({
            name: mcpQualifiedName(tool.serverId, tool.name),
            description: tool.description,
            serverId: tool.serverId,
            tool: tool.name,
          }))
        : undefined,
      mcpNote: mcp.ok ? undefined : mcp.reason,
    }, request.taskId)
    let result: RunAgentResult | undefined
    let networkEnabledForRun = request.networkEnabled
    let networkDegradedNote: string | undefined
    try {
      if (request.networkEnabled) {
        const attach = await attachNetworkWithRecovery(run.tabId, {
          captureBodies: request.captureNetworkBodies,
        })
        if (attach.tabId !== run.tabId) {
          run.tabId = attach.tabId
          this.writePresence(this.presenceFromRun(run))
          void this.bindRunTabGroup(run)
        }
        this.publishBackgroundRecord('run.network', {
          attached: attach.attached,
          message: attach.attached
            ? `debugger attached to tab ${attach.tabId}${attach.actions.length ? ` (${attach.actions.join(', ')})` : ''}`
            : `debugger attach failed (${attach.cause}): ${attach.error ?? 'unknown'}${attach.actions.length ? `; tried ${attach.actions.join(', ')}` : ''}`,
        })
        if (!attach.attached) {
          // Media extraction is timing-sensitive: the readiness probe may have
          // released the debugger just before the run starts. Keep a Network
          // plane for media runs so Runtime can retry after the first DOM
          // snapshot/card click instead of permanently removing `network`.
          const retryInsideRuntime = resolveDeliverable(request.task) === 'media'
          networkEnabledForRun = retryInsideRuntime
          networkDegradedNote = retryInsideRuntime ? undefined : formatNetworkDegradedNote(attach)
          this.publishBackgroundRecord('run.note', {
            topic: 'network_recovery',
            text: retryInsideRuntime
              ? `${formatNetworkDegradedNote(attach)}媒体任务保留 Network Plane，Runtime 将在页面稳定后重试。`
              : networkDegradedNote ?? formatNetworkDegradedNote(attach),
          })
        }
      }
      result = await runAgent({
        task: request.task,
        taskAnchor: request.taskAnchor,
        runId: request.id,
        taskId: request.taskId,
        dom: createChromeDomPlane(() => run.tabId),
        tabs: createChromeTabsPlane({
          getActiveTabId: () => run.tabId,
          onSwitch: (tabId) => {
            const previousTabId = run.tabId
            run.tabId = tabId
            this.writePresence(this.presenceFromRun(run))
            void this.bindRunTabGroup(run)
            if (request.sessionId) {
              run.sessionWrite = run.sessionWrite
                .then(async () => {
                  const tab = await chrome.tabs.get(tabId)
                  await updateSessionPage(request.sessionId!, {
                    tabId,
                    url: tab.url,
                    title: tab.title,
                  })
                })
                .catch(() => {})
            }
            if (request.networkEnabled && previousTabId !== tabId) {
              void detachNetwork(previousTabId)
              void attachNetwork(tabId, { captureBodies: request.captureNetworkBodies }).then((attached) => {
                this.publishBackgroundRecord('run.network', {
                  attached: attached.attached,
                  message: attached.attached
                    ? `debugger moved to tab ${tabId}`
                    : `debugger move failed: ${attached.error ?? 'unknown error'}`,
                })
              })
            }
            this.persistRun()
          },
        }),
        scripts: createChromeScriptPlane(),
        recipes: createChromeRecipePlane(() => run.tabId),
        search: createWebSearchPlane(),
        fetch: createFetchTextPlane(),
        network: networkEnabledForRun
          ? createChromeNetworkPlane(() => run.tabId, {
              captureBodies: request.captureNetworkBodies,
              getSignal: () => abort.signal,
            })
          : undefined,
        networkDegradedNote,
        skillGuidance: request.skillGuidance,
        skills: request.skillRegistry,
        threadContext: request.threadContext,
        allowedTools: request.allowedTools,
        llm: request.llm,
        mcpTools: mcp.ok ? mcp.mcpTools : undefined,
        callMcpTool: mcp.ok ? mcp.callMcpTool : undefined,
        allowDomInject: request.allowDomInject,
        allowNetworkIntercept: request.allowNetworkIntercept,
        maxSteps: request.maxSteps,
        sameFailureLimit: request.sameFailureLimit,
        runTimeoutMs: request.runTimeoutMs,
        runTokenBudget: request.runTokenBudget,
        maxInputTokens: request.maxInputTokens,
        signal: abort.signal,
        pause,
        queue,
        hitl,
        hitlPolicy: request.hitlPolicy,
        rollbackUrlDrift: request.rollbackUrlDrift,
        vision: request.visionEnabled === true,
        imageDataUrl: request.imageDataUrl,
        imageLabel: request.imageLabel,
        workspace: createChromeWorkspacePlane(),
        workspaceThread: request.sessionId
          ? await (async () => {
              const session = await getSession(request.sessionId!)
              const threadId = session?.threadId ?? request.sessionId!
              return {
                threadId,
                slug: workspaceSlug(session?.task ?? request.task),
                title: session?.task ?? request.task,
                runId: request.id,
              }
            })()
          : { threadId: request.id, slug: workspaceSlug(request.task), title: request.task, runId: request.id },
        locale: await loadResolvedLocale(),
        parentSessionId: request.sessionId,
        anchorTabId: run.tabId,
        createLeafPlanes: ({ anchorTabId }) => {
          const scope = createEphemeralTabScope(anchorTabId)
          return {
            dom: createChromeDomPlane(() => scope.getActiveTabId()),
            tabs: scope.tabs,
            dispose: () => scope.dispose(),
          }
        },
        onLeafSessionStart: async ({ childRunId, brief, index }) => {
          if (!request.sessionId) return
          const parent = await getSession(request.sessionId)
          const leaf = await createLeafSession({
            parentSessionId: request.sessionId,
            parentRunId: request.id,
            leafRunId: childRunId,
            threadId: parent?.threadId,
            task: `[leaf ${index + 1}] ${brief.slice(0, 160)}`,
          })
          run.leafSessions.set(childRunId, leaf.id)
          return leaf.id
        },
        onLeafRecord: (record) => {
          const leafSessionId = run.leafSessions.get(record.runId)
          if (leafSessionId) {
            run.sessionWrite = run.sessionWrite
              .then(() => appendSessionRecord(leafSessionId, record))
              .catch(() => {})
          }
          const line = leafProgressLine(record)
          if (line) {
            this.publishBackgroundRecord('run.note', { topic: 'subtask', text: line })
          }
        },
        onLeafSessionComplete: ({ childRunId, status }) => {
          const leafSessionId = run.leafSessions.get(childRunId)
          if (!leafSessionId) return
          void completeLeafSession(leafSessionId, status)
        },
        onRecord: (record) => this.notifyRunRecord(run, record),
      })
      if (result.status === 'cancelled') {
        this.publishBackgroundRecord('run.error', { message: result.result ?? 'Stopped by user', code: 'cancelled' })
      } else if (result.status === 'max_steps') {
        this.publishBackgroundRecord('run.error', { message: result.result ?? 'Agent step limit reached', code: 'max_steps' })
      } else if (result.status === 'error') {
        this.publishBackgroundRecord('run.error', { message: result.result ?? 'Agent run failed' })
      } else if (result.status === 'blocked') {
        this.publishBackgroundRecord('run.error', { message: result.result ?? 'Agent run blocked', code: 'blocked' })
      }
      if (request.sessionId) {
        await run.sessionWrite
        await completeSession(
          request.sessionId,
          result.status === 'done'
            ? 'success'
            : result.status === 'ask_user'
              ? 'waiting'
              : result.status === 'cancelled'
                ? 'cancelled'
                : 'failed',
          result.result ?? result.status
        )
      }
      if (result.status === 'done' && result.recordedActions.length) {
        const session = request.sessionId ? await getSession(request.sessionId) : undefined
        const forged = await forgePlaybookAfterSuccessfulRun({
          task: request.task,
          recordedActions: result.recordedActions,
          sessionId: request.sessionId,
          pageUrl: session?.page?.url,
        }).catch(() => null)
        if (forged) {
          this.publishBackgroundRecord('run.note', {
            topic: 'playbook',
            text: `Playbook forged ${forged.id} (${forged.steps} steps)`,
          })
        }
        const learned = await learnSiteRecipeFromRun({
          task: request.task,
          recordedActions: result.recordedActions,
          url: session?.page?.url,
        }).catch(() => null)
        if (learned) {
          this.publishBackgroundRecord('run.note', {
            topic: 'recipe',
            text: `Site recipe learned ${learned.id} (${learned.steps.length} steps)`,
          })
        }
        if (resolveTaskIntent(request.task) === 'media_extract') {
          this.publishBackgroundRecord('run.note', {
            topic: 'script',
            text:
              '视频落盘：~/NaviForge/scripts/download-hls.sh（Host 初始化后）或对话「用 script_save 写 ffmpeg 下载脚本」',
          })
        }
      }
      return result
    } finally {
      if (this.activeRun === run) {
        if (['WAITING_USER', 'PAUSED'].includes(run.status)) {
          this.writePresence(this.presenceFromRun(run, { waiting: true }))
        } else {
          this.stopPresenceBeat()
          this.writePresence(null)
          void chrome.storage.local.set({
            [STORAGE.activeRun]: {
              active: false,
              id: run.request.id,
              task: run.request.task,
              tabId: run.tabId,
              status: run.status,
              events: run.events,
              updatedAt: Date.now(),
            },
          })
          this.activeRun = null
          chrome.runtime
            .sendMessage({
              type: 'AGENT_RUN_FINISHED',
              runId: run.request.id,
              status: result?.status ?? 'error',
              answer: result?.result,
            })
            .catch(() => {})
        }
      }
    }
  }

  /** Host poll tasks share the same run loop as UI runs — single owner. */
  async runHostPollTask(opts: {
    hostTaskId: string
    instruction: string
    tabId: number
    llm: LlmConfig
    useNetwork: boolean
    privacy: typeof DEFAULT_PRIVACY
    skills: Skill[]
  }): Promise<RunAgentResult> {
    if (this.hasActiveRun()) {
      throw new Error('Another agent run is active')
    }
    const request = buildHostPollRunRequest(opts)
    const result = await this.start(request)
    if (!result) throw new Error('Host run produced no result')
    return result
  }

  private stopPresenceBeat(): void {
    if (this.presenceBeat != null) {
      clearInterval(this.presenceBeat)
      this.presenceBeat = undefined
    }
  }

  private presenceFromRun(run: ActiveRun, extra?: Partial<AgentPresence>): AgentPresence {
    const waiting =
      extra?.waiting !== undefined
        ? extra.waiting
        : run.status === 'WAITING_USER' || run.status === 'PAUSED'
    return {
      running: true,
      tabId: run.tabId,
      heartbeat: Date.now(),
      task: run.request.task,
      action: extra?.action ?? run.lastAction,
      waiting,
    }
  }

  private writePresence(presence: AgentPresence | null): void {
    if (!presence) {
      void chrome.storage.local.remove(STORAGE.agentPresence)
      return
    }
    void chrome.storage.local.set({ [STORAGE.agentPresence]: presence })
  }

  private startPresenceBeat(run: ActiveRun): void {
    this.stopPresenceBeat()
    this.writePresence(this.presenceFromRun(run))
    this.presenceBeat = setInterval(() => {
      if (this.activeRun !== run) {
        this.stopPresenceBeat()
        return
      }
      this.writePresence(this.presenceFromRun(run))
    }, 1_000)
  }

  private async bindRunTabGroup(run: ActiveRun): Promise<void> {
    const groupId = await pinAgentTabGroup(
      run.tabId,
      formatAgentGroupTitle(run.request.task),
      colorForAgentTask(run.request.id || run.request.task),
      run.groupId
    )
    if (groupId != null) run.groupId = groupId
  }

  private persistRun(): void {
    if (!this.activeRun) {
      this.stopPresenceBeat()
      this.writePresence(null)
      void chrome.storage.local.remove(STORAGE.activeRun)
      return
    }
    void chrome.storage.local.set({
      [STORAGE.activeRun]: {
        active: true,
        id: this.activeRun.request.id,
        task: this.activeRun.request.task,
        tabId: this.activeRun.tabId,
        status: this.activeRun.status,
        events: this.activeRun.events,
        updatedAt: Date.now(),
      },
    })
  }

  private notifyRunRecord(run: ActiveRun, record: TraceRecord): void {
    if (record.parentRunId && record.runId !== run.request.id) return
    run.events = [...run.events.slice(-199), record]
    if (record.type === 'run.error') {
      run.status = record.payload.code === 'cancelled' ? 'CANCELLED' : 'FAILED'
    }
    if (record.type === 'run.ask') run.status = 'WAITING_USER'
    if (record.type === 'tool.result') run.lastAction = record.payload.tool
    this.writePresence(this.presenceFromRun(run))
    this.persistSessionRecord(run.request.sessionId, record, run)
    chrome.runtime
      .sendMessage({ type: 'AGENT_RUN_EVENT', runId: run.request.id, event: record })
      .catch(() => {})
  }

  private publishRunRecord(record: TraceRecord): void {
    if (!this.activeRun) return
    this.notifyRunRecord(this.activeRun, record)
    this.persistRun()
  }

  private publishBackgroundRecord<Type extends TraceRecordType>(
    type: Type,
    payload: TraceRecordPayload[Type],
    taskId?: string
  ): void {
    if (!this.activeRun) return
    this.publishRunRecord(createTraceRecord({ type, payload, runId: this.activeRun.request.id, taskId }))
  }

  private persistSessionRecord(
    sessionId: string | undefined,
    record: TraceRecord,
    run: ActiveRun | null = this.activeRun
  ): void {
    if (!run || !sessionId || run.request.sessionId !== sessionId) return
    run.sessionWrite = run.sessionWrite.then(() => appendSessionRecord(sessionId, record)).catch(() => {})
  }
}

export const runSupervisor = new RunSupervisor()
