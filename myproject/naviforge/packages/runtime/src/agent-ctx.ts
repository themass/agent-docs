import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'
import type { NetworkPlane } from '@naviforge/network-plane'
import { formatDigest } from '@naviforge/network-plane'
import type { RecordedDomAction } from '@naviforge/playbook'
import { createTraceRecord, type TraceRecord, type TraceRecordPayload, type TraceRecordType } from '@naviforge/session'
import { resolveTaskScope, type TaskScope } from '@naviforge/policy'
import type { OpenAiFunctionTool, ToolCall, ToolResult } from '@naviforge/shared'
import { buildChatTools } from '@naviforge/shared'

import type {
  AgentOptions,
  ExternalMcpTool,
  HitlController,
  MessageQueue,
  PauseController,
  RunAgentResult,
} from './agent.js'
import { createRunHooks } from './builtin-hooks.js'
import type { HookPipeline } from './hooks.js'
import { RunLedger } from './ledger.js'
import type { LlmConfig } from './llm.js'
import {
  bareSkillId,
  observationDedupeKey,
  urlsMatchForReuse,
  type ThreadContext,
  type ThreadReuse,
} from './loop-gates.js'
import {
  createAgentGates,
  recordRunTab,
  resetTurnGates,
  type AgentGates,
} from './loop-gate-state.js'
import { composeSystemPrompt, compileUserPrompt } from './prompt.js'
import { resolveTaskMode } from './task-classifier.js'
import type { RecoveryPlan } from './recovery.js'
import type { ModelDecision } from './failure.js'
import { DEFAULT_RUN_LIMITS } from './run-limits.js'
import type { SearchPlane } from './search-plane.js'
import type { FetchPlane } from './fetch-plane.js'
import type { RecipePlane } from './recipe-plane.js'
import type { ScriptPlane } from './script-plane.js'
import type { TabsPlane } from './tabs-plane.js'
import { createContextCompactor } from './context-compaction.js'
import { WORKING_SET, type ContextCompactor } from './working-set.js'
import type { WorkspacePlane } from './workspace-plane.js'

export type SkillSpec = NonNullable<AgentOptions['skills']>[number]

export type AgentPlanes = {
  /** dom_* / dom_read → dom-plane (extension content + chrome-dom-plane) */
  dom: DomPlane
  /** network_read / network_intercept → network-plane */
  network?: NetworkPlane
  /** tabs_* → tabs-plane */
  tabs?: TabsPlane
  /** web_search → search-plane */
  search?: SearchPlane
  /** fetch_text → fetch-plane */
  fetch?: FetchPlane
  /** script_* → script-plane */
  scripts?: ScriptPlane
  /** site recipe preflight / promotion */
  recipes?: RecipePlane
  /** workspace / workspace_* → workspace-plane (host helper) */
  workspace?: WorkspacePlane
}

/** I/O slice for `execTurn`. Not a third domain object — a bag of Agent/Ctx fields the tool runner may read. */
export type AgentIo = {
  runId: string
  planes: AgentPlanes
  snap: DomSnapshot
  taskScope: TaskScope
  llm: LlmConfig
  signal?: AbortSignal
  hitlPolicy: NonNullable<AgentOptions['hitlPolicy']>
  rollbackUrlDrift: boolean
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  callMcpTool?: AgentOptions['callMcpTool']
  mcpTools?: ExternalMcpTool[]
  skills?: AgentOptions['skills']
  mainProbe?: AgentOptions['mainProbe']
  visionShot?: { dataUrl?: string }
  emit?: (record: TraceRecord) => void
  chargeTokens?: (usage: { promptTokens: number; completionTokens: number; totalTokens: number }) => void
  createRecord: <Type extends TraceRecordType>(
    type: Type,
    payload: TraceRecordPayload[Type]
  ) => TraceRecord
  workspaceThread?: { threadId: string; slug?: string; title?: string; runId?: string }
  locale?: string
  parentSessionId?: AgentOptions['parentSessionId']
  anchorTabId?: AgentOptions['anchorTabId']
  createLeafPlanes?: AgentOptions['createLeafPlanes']
  onLeafRecord?: AgentOptions['onLeafRecord']
  onLeafSessionStart?: AgentOptions['onLeafSessionStart']
  onLeafSessionComplete?: AgentOptions['onLeafSessionComplete']
  gates: AgentGates
}

export type AgentPolicy = {
  hitlPolicy: NonNullable<AgentOptions['hitlPolicy']>
  allowDomInject: boolean
  allowNetworkIntercept: boolean
  allowedTools?: Set<string>
  rollbackUrlDrift: boolean
}

export type AgentLimits = {
  maxSteps: number
  sameFailureLimit: number
  sameActionLimit: number
  runTimeoutMs: number
  runTokenBudget: number
  maxInputTokens: number
}

export type AgentPrompt = {
  system: string
  user: string
  thread?: ThreadContext
  loadedSkillText?: string
}

/**
 * Capability bag assembled once from `AgentOptions` (Pi `Agent`, MAF `Agent`,
 * DSH seams). Mutating `skills` / `mcpTools` / `skillGuidance` here is how
 * `onStart` hooks change what the run can do. The loop lives in `agent.ts`.
 */
export class Agent {
  readonly opts: AgentOptions
  readonly runId: ReturnType<typeof crypto.randomUUID>
  readonly planes: AgentPlanes
  readonly llm: LlmConfig
  skills: SkillSpec[]
  mcpTools: ExternalMcpTool[]
  skillGuidance: string
  threadContext?: ThreadContext
  readonly policy: AgentPolicy
  readonly profile?: NonNullable<AgentOptions['runProfile']>
  readonly limits: AgentLimits
  readonly contextCompactor: ContextCompactor
  readonly hooks: HookPipeline
  readonly hitl?: HitlController
  readonly queue?: MessageQueue
  readonly pause?: PauseController
  readonly signal?: AbortSignal
  readonly callMcpTool?: AgentOptions['callMcpTool']
  readonly mainProbe?: AgentOptions['mainProbe']
  readonly vision: boolean

  /**
   * Bound by `agent.ts` (`Agent.prototype.run`) so this module does not import
   * the loop.
   */
  run(): Promise<RunAgentResult> {
    throw new Error('Agent.run is attached by the runtime loop')
  }

  constructor(opts: AgentOptions) {
    this.runId = opts.runId ?? crypto.randomUUID()
    this.opts = { ...opts, runId: this.runId }
    this.planes = {
      dom: opts.dom,
      network: opts.network,
      tabs: opts.tabs,
      search: opts.search,
      fetch: opts.fetch,
      scripts: opts.scripts,
      recipes: opts.recipes,
      workspace: opts.workspace,
    }
    this.llm = opts.llm
    this.skills = [...(opts.skills ?? [])]
    this.mcpTools = [...(opts.mcpTools ?? [])]
    this.skillGuidance = opts.skillGuidance ?? ''
    this.threadContext = opts.threadContext
    this.policy = {
      hitlPolicy: opts.hitlPolicy ?? 'balanced',
      allowDomInject: opts.allowDomInject === true,
      allowNetworkIntercept: opts.allowNetworkIntercept === true,
      allowedTools: opts.allowedTools?.length ? new Set(opts.allowedTools) : undefined,
      rollbackUrlDrift: opts.rollbackUrlDrift !== false,
    }
    this.profile = opts.runProfile
    this.limits = {
      maxSteps: opts.maxSteps ?? DEFAULT_RUN_LIMITS.maxSteps,
      sameFailureLimit: opts.sameFailureLimit ?? DEFAULT_RUN_LIMITS.sameFailureLimit,
      sameActionLimit: opts.sameActionLimit ?? DEFAULT_RUN_LIMITS.sameActionLimit,
      runTimeoutMs: opts.runTimeoutMs ?? DEFAULT_RUN_LIMITS.runTimeoutMs,
      runTokenBudget: opts.runTokenBudget ?? opts.tokenBudget ?? DEFAULT_RUN_LIMITS.runTokenBudget,
      maxInputTokens: opts.maxInputTokens ?? DEFAULT_RUN_LIMITS.maxInputTokens,
    }
    this.contextCompactor =
      opts.contextCompactor ?? createContextCompactor({ llm: opts.llm, signal: opts.signal })
    this.hooks = createRunHooks(
      this.limits.sameFailureLimit,
      opts.hooks ?? [],
      opts.runProfile?.name === 'readonly-child' ? 4 : 1
    ).pipeline
    this.hitl = opts.hitl
    this.queue = opts.queue
    this.pause = opts.pause
    this.signal = opts.signal
    this.callMcpTool = opts.callMcpTool
    this.mainProbe = opts.mainProbe
    this.vision = opts.vision === true
  }
}

/**
 * Per-run mutable working set passed to every hook (MAF `AgentContext`, Pi
 * `AgentContext` snapshot + loop locals). Assemble once after the first
 * snapshot; `beforeModel` refreshes `prompt` / `tools` / `messages`.
 */
export class AgentCtx {
  readonly agent: Agent
  readonly ledger = new RunLedger()
  readonly runId: string
  task: string
  taskId?: string
  turnIndex: number | undefined
  snap: DomSnapshot
  taskScope: TaskScope
  runTotalTokens = 0
  prompt: AgentPrompt
  tools: OpenAiFunctionTool[]
  skills: SkillSpec[]
  skillGuidance: string
  /** Projected working set (not the full ledger). Hooks may replace this. */
  messages: string[] = []
  imageDataUrl?: string
  networkText = 'NETWORK: (disabled)'
  /** Deterministic page signal hydrate (inline scripts, DOM resources, network). */
  pageSignalsText = ''
  pageFrictionText = ''
  completion?: { content: string; reasoning?: string; toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }> }
  decision?: ModelDecision
  toolCall?: ToolCall
  toolResult?: ToolResult
  gates: AgentGates
  recordedActions: RecordedDomAction[] = []
  recoveries: RecoveryPlan[] = []
  metadata: Record<string, unknown> = {}
  allowedTools?: Set<string>
  visionShot: { dataUrl?: string } = {}
  /** Formatted execTurn trace for this step; set before `afterTool`. */
  toolTrace?: string
  readonly reuse: ThreadReuse

  constructor(agent: Agent, snap: DomSnapshot) {
    this.agent = agent
    this.runId = agent.runId
    this.snap = snap
    this.task = agent.opts.task
    this.taskId = agent.opts.taskId
    this.taskScope = resolveTaskScope(this.task)
    this.skillGuidance = agent.skillGuidance
    this.skills = [...agent.skills]
    this.allowedTools = agent.policy.allowedTools ? new Set(agent.policy.allowedTools) : undefined
    this.prompt = {
      system: composeSystemPrompt(agent.skillGuidance, {
        hasMcpTools: agent.mcpTools.length > 0,
      }),
      user: '',
      thread: agent.threadContext,
    }
    const profileMcpTools = agent.profile?.allowReadonlyMcp
      ? agent.mcpTools.filter((tool) => tool.readonly)
      : agent.mcpTools
    this.tools = buildChatTools(
      profileMcpTools,
      agent.profile ? { only: agent.profile.allowedTools } : undefined
    )
    this.reuse = agent.threadContext?.reuse ?? { skillIds: [] }
    this.gates = createAgentGates(agent.limits.sameActionLimit)
    for (const id of this.reuse.skillIds) this.gates.loadedSkillIds.add(bareSkillId(id))
    if (typeof agent.opts.anchorTabId === 'number') {
      recordRunTab(this.gates, agent.opts.anchorTabId)
    }
    const taskPayload: import('@naviforge/session').TraceRecordPayload['user.task'] = { text: this.task }
    if (agent.opts.imageDataUrl) {
      taskPayload.imageDataUrl = agent.opts.imageDataUrl
      if (agent.opts.imageLabel) taskPayload.imageLabel = agent.opts.imageLabel
      this.visionShot.dataUrl = agent.opts.imageDataUrl
    }
    const taskRecord = this.createRecord('user.task', taskPayload)
    this.ledger.append(taskRecord)
    this.agent.opts.onRecord?.(taskRecord)
    if (this.reuse.page && urlsMatchForReuse(this.reuse.page.url, snap.url)) {
      const readKey = observationDedupeKey('dom_read', snap.url, { mode: 'body' })
      if (readKey) {
        this.gates.seenObs.add(readKey)
        this.gates.lastObsByKey.set(readKey, this.reuse.page.evidence)
        this.recordNote(`PREFLIGHT: reuse ${this.reuse.page.evidence.slice(0, WORKING_SET.evidenceChars)}`)
      }
    }
  }

  createRecord<Type extends TraceRecordType>(
    type: Type,
    payload: TraceRecordPayload[Type]
  ): TraceRecord {
    return createTraceRecord({
      type,
      payload,
      runId: this.runId,
      parentRunId: this.agent.opts.parentRunId,
      taskId: this.taskId,
      turn: this.turnIndex,
    })
  }

  emit(record: TraceRecord): void {
    this.ledger.append(record)
    this.agent.opts.onRecord?.(record)
  }

  recordNote(line: string): void {
    this.emit(this.createRecord('run.note', { text: line, topic: 'internal' }))
  }

  chargeTokens(usage: { promptTokens: number; completionTokens: number; totalTokens: number }): void {
    this.runTotalTokens += usage.totalTokens
    this.emit(
      this.createRecord('metrics.tokens', {
        prompt: usage.promptTokens,
        completion: usage.completionTokens,
        total: usage.totalTokens,
        runTotal: this.runTotalTokens,
      })
    )
  }

  appendCompaction(payload: Extract<TraceRecord, { type: 'context.compaction' }>['payload']): void {
    this.emit(this.createRecord('context.compaction', payload))
  }

  recover(plan: RecoveryPlan): void {
    this.recoveries.push(plan)
    this.emit(this.createRecord('run.recovery', { strategy: plan.strategy, diagnostic: plan.diagnostic }))
  }

  /** Rebuild per-turn copies from the Agent bag. Extra hooks that must persist mutate `agent.*`. */
  syncFromAgent(): void {
    this.skills = [...this.agent.skills]
    this.skillGuidance = this.agent.skillGuidance
    this.allowedTools = this.agent.policy.allowedTools ? new Set(this.agent.policy.allowedTools) : undefined
    this.prompt.system = composeSystemPrompt(this.agent.skillGuidance, {
      hasMcpTools: this.agent.mcpTools.length > 0,
    })
    this.prompt.thread = this.agent.threadContext
    this.syncTools()
  }

  /** Rebuild `tools` from the Agent bag so a hook can add/remove MCP tools. */
  syncTools(): void {
    const profile = this.agent.profile
    const mcpTools = profile?.allowReadonlyMcp
      ? this.agent.mcpTools.filter((tool) => tool.readonly)
      : this.agent.mcpTools
    this.tools = buildChatTools(mcpTools, profile ? { only: profile.allowedTools } : undefined)
  }

  compileUser(): string {
    return compileUserPrompt(
      this.task,
      this.snap,
      this.messages,
      this.networkText,
      this.prompt.loadedSkillText ??
        (this.gates.loadedSkillBodies.length ? this.gates.loadedSkillBodies.join('\n---\n') : undefined),
      this.prompt.thread,
      this.agent.opts.locale,
      resolveTaskMode(this.task),
      this.pageSignalsText,
      this.pageFrictionText
    )
  }

  async refreshNetwork(): Promise<void> {
    const network = this.agent.planes.network
    if (!network) {
      this.networkText = 'NETWORK: (disabled)'
      return
    }
    let digest = await network.digest(10)
    if (!digest.ok) {
      await network.start()
      digest = await network.digest(10)
    }
    this.networkText = digest.ok ? formatDigest(digest.data) : `NETWORK: error ${digest.error.message}`
  }

  bindToolCall(decision: ModelDecision): void {
    this.toolCall = { tool: decision.call.tool, arguments: { ...decision.call.arguments } }
    this.toolResult = undefined
  }

  applyToolArgs(): void {
    if (!this.decision || !this.toolCall) return
    this.decision.call.arguments = this.toolCall.arguments
    this.decision.call.tool = this.toolCall.tool
  }

  io(): AgentIo {
    return {
      runId: this.runId,
      planes: this.agent.planes,
      snap: this.snap,
      taskScope: this.taskScope,
      llm: this.agent.llm,
      signal: this.agent.signal,
      hitlPolicy: this.agent.policy.hitlPolicy,
      rollbackUrlDrift: this.agent.policy.rollbackUrlDrift,
      allowDomInject: this.agent.policy.allowDomInject,
      allowNetworkIntercept: this.agent.policy.allowNetworkIntercept,
      callMcpTool: this.agent.callMcpTool,
      mcpTools: this.agent.mcpTools,
      skills: this.skills,
      mainProbe: this.agent.mainProbe,
      visionShot: this.visionShot,
      emit: (record) => this.emit(record),
      chargeTokens: (usage) => this.chargeTokens(usage),
      createRecord: (type, payload) => this.createRecord(type, payload),
      workspaceThread: this.agent.opts.workspaceThread,
      locale: this.agent.opts.locale,
      parentSessionId: this.agent.opts.parentSessionId,
      anchorTabId: this.agent.opts.anchorTabId,
      createLeafPlanes: this.agent.opts.createLeafPlanes,
      onLeafRecord: this.agent.opts.onLeafRecord,
      onLeafSessionStart: this.agent.opts.onLeafSessionStart,
      onLeafSessionComplete: this.agent.opts.onLeafSessionComplete,
      gates: this.gates,
    }
  }

  retarget(task: string, taskId?: string): void {
    this.task = task
    this.taskId = taskId
    this.turnIndex = undefined
    this.taskScope = resolveTaskScope(task)
    resetTurnGates(this.gates)
  }
}
