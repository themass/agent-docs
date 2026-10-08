import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'
import type { TabsPlane } from './tabs-plane.js'
import type { SearchPlane } from './search-plane.js'
import type { FetchPlane } from './fetch-plane.js'
import type { RecipePlane } from './recipe-plane.js'
import type { ScriptPlane } from './script-plane.js'
import type { WorkspacePlane } from './workspace-plane.js'
import type { NetworkPlane } from '@naviforge/network-plane'
import type { ToolResult } from '@naviforge/shared'
import { createTraceRecord, type TraceRecord, type TraceRecordPayload, type TraceRecordType } from '@naviforge/session'

import { Agent, AgentCtx } from './agent-ctx.js'
import { transitionCapability } from './capability-state.js'
import type { AgentHook, HookDecision } from './hooks.js'
import type { LlmConfig } from './llm.js'
import { classifyFailure, isAbortError, type RecoveryPlan } from './recovery.js'
import { fillCopy, uiCopy } from './ui-copy.js'
import type { ContextCompactor } from './working-set.js'
import { resolveTaskScope, type HitlPolicyMode } from '@naviforge/policy'
import { observationDedupeKey, type ThreadContext } from './loop-gates.js'
import { resetTurnGates } from './loop-gate-state.js'
import { runModelTurns } from './model-turns.js'
import { ensureAnchorTask, syncDeliverableFromTask } from './execution-task.js'
import { attachPageState } from './pi-run-loop.js'
import { READONLY_RUN_PROFILE, type RunProfile } from './run-profile.js'

import type { RecordedDomAction } from '@naviforge/playbook'

import { snapshotWithRetry } from './exec-turn.js'

export { formatActingDetail } from './acting-detail.js'
export {
  isToolAllowed,
  isCspEvalError,
  normalizeScrollArgs,
  formatReadPageTrace,
  formatExtractDomTrace,
  formatExtractContentTrace,
  formatToolTrace,
} from './exec-turn.js'
export { formatWebSearchTrace } from './search-plane.js'
export {
  clampFetchMaxChars,
  formatFetchTextTrace,
  normalizeFetchTextUrl,
} from './fetch-plane.js'
export {
  observationDedupeKey,
  actionLoopKey,
  createActionLoopGate,
  decideActionLoop,
  recordActionLoopSuccess,
  replayActionLoop,
  urlsMatchForReuse,
  bareSkillId,
  isPageReadTask,
  isResearchTask,
  resolveTaskMode,
  shouldHintListThenDetail,
  requestedList,
  requestedTopN,
  type ActionLoopCall,
  type ActionLoopGate,
  type ThreadContext,
  type ThreadReuse,
} from './loop-gates.js'
export { runModelTurns } from './model-turns.js'
export { PreflightHook } from './builtin-hooks.js'
export { Agent, AgentCtx } from './agent-ctx.js'
export { type AgentGates, createAgentGates, resetTurnGates } from './loop-gate-state.js'


export type { RecordedDomAction }

/**
 * Where an event sits in the loop. Stamped centrally by `runAgent`, so every
 * projection of the trace can group by task and turn without re-deriving order.
 * `turn` is absent for work that happens outside a model turn (setup, deterministic reads).
 */
export type TraceMeta = { runId?: string; taskId?: string; turn?: number; parentRunId?: string }

export type PauseController = {
  isPaused: () => boolean
  waitIfPaused: (signal?: AbortSignal) => Promise<void>
}

/** Blocks the agent until the UI answers an ask_user question. */
export type HitlController = {
  waitForReply: (question: string, signal?: AbortSignal) => Promise<string>
}

export type AgentOptions = {
  task: string
  /** Session goal for deliverable / routing when `task` is a continuation cue (继续, continue, …). */
  taskAnchor?: string
  /** Assigned by the run owner before runtime starts; all records share it. */
  runId?: ReturnType<typeof crypto.randomUUID>
  /** Parent run for a bounded readonly leaf. */
  parentRunId?: string
  /** Parent thread session id (leaf audit only). */
  parentSessionId?: string
  /** Parent-locked target tab; leaf ephemeral tabs must not switch this. */
  anchorTabId?: number
  /** Per-child ephemeral planes (isolated tab binding for parallel leaves). */
  createLeafPlanes?: (input: { childRunId: string; anchorTabId: number }) =>
    | Promise<{ dom: DomPlane; tabs?: TabsPlane; dispose: () => Promise<void> }>
    | { dom: DomPlane; tabs?: TabsPlane; dispose: () => Promise<void> }
  /** Leaf trace sink — never merged into the parent ledger. */
  onLeafRecord?: (record: import('@naviforge/session').TraceRecord) => void
  onLeafSessionStart?: (input: {
    childRunId: string
    brief: string
    index: number
  }) => Promise<void | string>
  onLeafSessionComplete?: (input: {
    childRunId: string
    status: 'success' | 'failed' | 'cancelled'
  }) => void
  /** Queue id of the first task, so per-task results stay attributable in the trace. */
  taskId?: string
  dom: DomPlane
  tabs?: TabsPlane
  search?: SearchPlane
  fetch?: FetchPlane
  scripts?: ScriptPlane
  recipes?: RecipePlane
  llm: LlmConfig
  network?: NetworkPlane
  skillGuidance?: string
  /**
   * Installed skills for progressive disclosure. Catalog (L1) goes in `skillGuidance`;
   * full bodies are returned only when the model calls `skill_load`.
   */
  skills?: Array<{
    id: string
    version: string
    description: string
    instructions: string
    tools?: string[]
    files?: string[]
  }>
  /** Bounded, compressed context from prior runs in the active chat thread. */
  threadContext?: ThreadContext
  /** Optional exact tool allowlist imposed by the selected skill. System terminal tools remain available. */
  allowedTools?: string[]
  /** Capability boundary for specialized runs. Normal runs omit this. */
  runProfile?: RunProfile
  mcpTools?: ExternalMcpTool[]
  callMcpTool?: (
    serverId: string,
    tool: string,
    args: Record<string, unknown>
  ) => Promise<ToolResult>
  /** Allow dom_inject kind=script (settings gate). */
  allowDomInject?: boolean
  /** Allow network_intercept / clearIntercepts (settings gate). */
  allowNetworkIntercept?: boolean
  maxSteps?: number
  /** Consecutive same tool+error.code failures before ask_user (default 2; 0 = off). */
  sameFailureLimit?: number
  /** Max successful identical screenshot/scroll/snapshot per URL before blocking (default 2; 0 = off). */
  sameActionLimit?: number
  /** Wall-clock limit for one Run in ms (default 8 min; 0 = off). */
  runTimeoutMs?: number
  /** Stop when cumulative LLM tokens reach this (default 200_000; 0 = off). */
  runTokenBudget?: number
  /** Maximum estimated tokens in one model input (system + user; 0 = off). */
  maxInputTokens?: number
  /** @deprecated Use `runTokenBudget`. */
  tokenBudget?: number
  /** Optional L2 semantic compactor; it never mutates the trace ledger. */
  contextCompactor?: ContextCompactor
  signal?: AbortSignal
  pause?: PauseController
  /** Dual queues: steer corrects mid-run; followUp starts after stop. */
  queue?: MessageQueue
  /** When set, ask_user waits for a reply instead of ending the run. */
  hitl?: HitlController
  /** ask_user policy: strict blocks clarifications; balanced default; permissive allows most. */
  hitlPolicy?: HitlPolicyMode
  /** Attempt history.back() after unexpected URL drift on stay-on-page tasks. */
  rollbackUrlDrift?: boolean
  /** MAIN-world read-only probe (extension provides; requires allowMainProbe setting). */
  mainProbe?: (expression: string) => Promise<ToolResult<{ value: unknown }>>
  /** Attach visible-tab screenshot to each LLM user message (multimodal models). */
  vision?: boolean
  /** User-attached image for the initial task (composer / screenshot studio). */
  imageDataUrl?: string
  imageLabel?: string
  /** On-disk user workspace (Host). Screenshots and JSONL go here. */
  workspace?: WorkspacePlane
  workspaceThread?: { threadId: string; slug?: string; title?: string; runId?: string }
  /** UI locale for HITL / status copy and Reply language fallback (`en` | `zh-CN` | `es`). */
  locale?: string
  /** Extension already tried CDP recovery; run continues without Network plane. */
  networkDegradedNote?: string
  onRecord?: (record: import('@naviforge/session').TraceRecord) => void
  /** Lets a child charge model usage to its owning run. */
  onTokenUsage?: (usage: { promptTokens: number; completionTokens: number; totalTokens: number }) => void
  saveCheckpoint?: (step: number, summary: string) => Promise<void>
  /**
   * Extra hooks after the stock pipeline (working-set, protocol, tool gates).
   * May rewrite `ctx.prompt` / `ctx.tools` / `ctx.skills` / `ctx.messages`.
   */
  hooks?: AgentHook[]
}

export type ExternalMcpTool = {
  serverId: string
  serverName: string
  name: string
  description?: string
  inputSchema: unknown
  /** Explicitly approved for a readonly child profile. */
  readonly?: boolean
}

export { READONLY_RUN_PROFILE, type RunProfile }

export type RunAgentResult = {
  status: 'done' | 'ask_user' | 'blocked' | 'error' | 'cancelled' | 'max_steps'
  result?: string
  /** Successful DOM click/type only — for Teach → Playbook. */
  recordedActions: RecordedDomAction[]
  finalUrl?: string
  recoveries: RecoveryPlan[]
}

export function createPauseController(): PauseController & {
  pause: () => void
  resume: () => void
} {
  let paused = false
  let wake: (() => void) | null = null
  return {
    isPaused: () => paused,
    pause: () => {
      paused = true
    },
    resume: () => {
      paused = false
      wake?.()
      wake = null
    },
    waitIfPaused: async (signal?: AbortSignal) => {
      while (paused) {
        signal?.throwIfAborted()
        await new Promise<void>((resolve, reject) => {
          let settled = false
          const finish = (fn: () => void) => {
            if (settled) return
            settled = true
            signal?.removeEventListener('abort', onAbort)
            fn()
          }
          const onAbort = () => finish(() => reject(new DOMException('Aborted', 'AbortError')))
          if (signal?.aborted) {
            onAbort()
            return
          }
          signal?.addEventListener('abort', onAbort, { once: true })
          wake = () => finish(resolve)
        })
      }
    },
  }
}

/** Promise gate for ask_user ↔ UI reply (HITL). */
export function createHitlGate(): HitlController & {
  reply: (text: string) => boolean
  isWaiting: () => boolean
  question: () => string | null
  cancelWaiting: () => void
} {
  let pending: {
    question: string
    resolve: (text: string) => void
    reject: (err: Error) => void
    onAbort: () => void
    signal?: AbortSignal
  } | null = null
  // ponytail: UI may reply after ask_user emit before waitForReply registers; buffer one.
  let buffered: string | null = null

  const clear = () => {
    if (!pending) return
    pending.signal?.removeEventListener('abort', pending.onAbort)
    pending = null
  }

  return {
    isWaiting: () => pending !== null || buffered !== null,
    question: () => pending?.question ?? null,
    reply(text) {
      const value = text.trim()
      if (!value) return false
      if (pending) {
        const { resolve } = pending
        clear()
        buffered = null
        resolve(value)
        return true
      }
      buffered = value
      return true
    },
    cancelWaiting() {
      buffered = null
      if (!pending) return
      const { reject } = pending
      clear()
      reject(new DOMException('HITL cancelled', 'AbortError'))
    },
    waitForReply(question, signal) {
      if (pending) {
        const { reject } = pending
        clear()
        reject(new Error('HITL superseded'))
      }
      if (buffered) {
        const answer = buffered
        buffered = null
        return Promise.resolve(answer)
      }
      return new Promise<string>((resolve, reject) => {
        const onAbort = () => {
          clear()
          reject(new DOMException('Aborted', 'AbortError'))
        }
        if (signal?.aborted) {
          reject(new DOMException('Aborted', 'AbortError'))
          return
        }
        signal?.addEventListener('abort', onAbort, { once: true })
        pending = { question, resolve, reject, onAbort, signal }
      })
    },
  }
}

export type QueuedTask = {
  id: string
  text: string
}

export function createQueuedTask(text: string, id?: string): QueuedTask | null {
  const value = text.trim()
  if (!value) return null
  return { id: id ?? crypto.randomUUID(), text: value }
}

export type MessageQueue = {
  steer: (text: string) => void
  followUp: (text: string, id?: string) => QueuedTask | null
  listFollowUps: () => QueuedTask[]
  setFollowUps: (tasks: QueuedTask[]) => void
  updateFollowUp: (id: string, text: string) => void
  removeFollowUp: (id: string) => void
  moveFollowUp: (from: number, to: number) => void
  drainSteering: () => string[]
  /** Take the next queued task for sequential execution. */
  drainNextFollowUp: () => QueuedTask | null
  pending: () => { steering: number; followUp: number }
  clear: () => void
}

/** Steering applies immediately; follow-ups run one task at a time. */
export function createMessageQueue(): MessageQueue {
  const steering: string[] = []
  const followUps: QueuedTask[] = []
  return {
    steer(text) {
      const value = text.trim()
      if (value) steering.push(value)
    },
    followUp(text, id) {
      const item = createQueuedTask(text, id)
      if (!item || followUps.some((task) => task.id === item.id)) return null
      followUps.push(item)
      return item
    },
    listFollowUps() {
      return followUps.map((task) => ({ ...task }))
    },
    setFollowUps(tasks) {
      followUps.length = 0
      const seenIds = new Set<string>()
      for (const task of tasks) {
        const item = createQueuedTask(task.text, task.id)
        if (item && !seenIds.has(item.id)) {
          seenIds.add(item.id)
          followUps.push(item)
        }
      }
    },
    updateFollowUp(id, text) {
      const index = followUps.findIndex((task) => task.id === id)
      if (index < 0) return
      const value = text.trim()
      if (!value) followUps.splice(index, 1)
      else followUps[index] = { ...followUps[index]!, text: value }
    },
    removeFollowUp(id) {
      const index = followUps.findIndex((task) => task.id === id)
      if (index >= 0) followUps.splice(index, 1)
    },
    moveFollowUp(from, to) {
      if (from < 0 || from >= followUps.length || to < 0 || to >= followUps.length) return
      const [item] = followUps.splice(from, 1)
      followUps.splice(to, 0, item)
    },
    drainSteering() {
      return steering.splice(0)
    },
    drainNextFollowUp() {
      return followUps.shift() ?? null
    },
    pending() {
      return { steering: steering.length, followUp: followUps.length }
    },
    clear() {
      steering.length = 0
      followUps.length = 0
    },
  }
}

export async function runAgent(opts: AgentOptions): Promise<RunAgentResult> {
  const agent = new Agent(opts)
  return runPiAgentLoop(agent)
}

/** Outer Pi loop: one task, then follow-up. Inner turns live in `runModelTurns`. */
async function runPiAgentLoop(agent: Agent): Promise<RunAgentResult> {
  const opts = agent.opts
  const planes = agent.planes
  let runStartedAt = Date.now()
  let hitlPauseAt: number | null = null

  const pauseWallClock = (): void => {
    if (hitlPauseAt == null) hitlPauseAt = Date.now()
  }
  const resumeWallClock = (): void => {
    if (hitlPauseAt != null) {
      runStartedAt += Date.now() - hitlPauseAt
      hitlPauseAt = null
    }
  }
  const wallClockElapsed = (): number => Date.now() - runStartedAt
  const finish = (
    ctx: AgentCtx,
    status: RunAgentResult['status'],
    result?: string
  ): RunAgentResult => ({
    status,
    result,
    recordedActions: ctx.recordedActions,
    finalUrl: ctx.snap.url,
    recoveries: ctx.recoveries,
  })

  const emitEarly = <Type extends TraceRecordType>(
    type: Type,
    payload: TraceRecordPayload[Type]
  ): void => {
    opts.onRecord?.(
      createTraceRecord({
        type,
        payload,
        runId: agent.runId,
        parentRunId: opts.parentRunId,
        taskId: opts.taskId,
      })
    )
  }

  if (planes.network && agent.profile?.manageNetwork !== false) {
    const digestProbe = await planes.network.digest(1)
    if (digestProbe.ok) {
      emitEarly('run.log', { message: 'network digest ok (skip duplicate attach)' })
    } else {
      const started = await planes.network.start()
      if (started.ok) {
        emitEarly('run.log', { message: 'network debugger attached' })
        emitEarly('run.network', { attached: true, message: 'debugger attached' })
      }
    }
  }

  const first = await snapshotWithRetry(planes.dom)
  if (!first.ok) {
    emitEarly('run.error', { message: first.error.message })
    return {
      status: 'error',
      result: first.error.message,
      recordedActions: [],
      recoveries: [classifyFailure(first.error)],
    }
  }

  const ctx = new AgentCtx(agent, first.data)
  if (opts.networkDegradedNote?.trim()) {
    ctx.agent.planes.network = undefined
    ctx.runtimeState = {
      ...ctx.runtimeState,
      capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'unavailable', {
        reason: opts.networkDegradedNote.trim(),
        incrementAttempt: true,
      }),
    }
    ctx.networkText = 'NETWORK: (degraded — DOM-only for this run)'
    ctx.recordNote(opts.networkDegradedNote.trim())
    ctx.syncTools()
  }
  await attachPageState(ctx)
  const pipeline = agent.hooks

  const noteUsage = (usage?: { promptTokens: number; completionTokens: number; totalTokens: number }) => {
    if (!usage) return
    ctx.runTotalTokens += usage.totalTokens
    opts.onTokenUsage?.(usage)
    ctx.emit(
      ctx.createRecord('metrics.tokens', {
        prompt: usage.promptTokens,
        completion: usage.completionTokens,
        total: usage.totalTokens,
        runTotal: ctx.runTotalTokens,
      })
    )
  }
  const budgetExceeded = (): string | null => {
    const { runTimeoutMs, runTokenBudget } = agent.limits
    if (runTimeoutMs > 0 && wallClockElapsed() >= runTimeoutMs) {
      return fillCopy(uiCopy(agent.opts.locale).timeout, {
        minutes: Math.round(runTimeoutMs / 60_000),
      })
    }
    if (runTokenBudget > 0 && ctx.runTotalTokens >= runTokenBudget) {
      return fillCopy(uiCopy(agent.opts.locale).tokenBudget, {
        budget: runTokenBudget,
        used: ctx.runTotalTokens,
      })
    }
    return null
  }
  const awaitHitl = async (
    question: string,
    stopOnCancel: boolean
  ): Promise<'continue' | 'stop' | 'park'> => {
    pauseWallClock()
    try {
      if (!agent.hitl) {
        ctx.emit(
          ctx.createRecord('run.ask', {
            question,
            wait: 'user',
          })
        )
        return 'park'
      }
      const waiting = agent.hitl.waitForReply(question, agent.signal)
      ctx.emit(
        ctx.createRecord('run.ask', {
          question,
          wait: 'user',
        })
      )

      const answer = await waiting
      ctx.recordNote(`USER ANSWER: USER ANSWER to "${question}": ${answer}`)
      ctx.emit(ctx.createRecord('run.log', { message: `↩ hitl: ${answer}` }))
      if (stopOnCancel && /^(停止|stop|取消|cancel)\b/i.test(answer.trim())) return 'stop'
      return 'continue'
    } finally {
      resumeWallClock()
    }
  }
  const injectSteering = () => {
    const steers = agent.queue?.drainSteering() ?? []
    if (!steers.length) return
    for (const text of steers) {
      ctx.recordNote(
        `USER CORRECTION: USER CORRECTION (obey over prior plan; stay on current page unless correction says otherwise): ${text}`
      )
    }
    ctx.emit(ctx.createRecord('user.steer', { texts: steers, phase: 'pre_model' }))
  }
  const maybeFollowUpNext = (previous: string): boolean => {
    const next = agent.queue?.drainNextFollowUp() ?? null
    if (!next) return false
    ctx.recordNote(`FOLLOW-UP: previous=${previous.slice(0, 200)}`)
    ctx.recordNote(`FOLLOW-UP: NEW TASK: ${next.text}`)
    ctx.retarget(next.text, next.id)
    ctx.emit(ctx.createRecord('user.task', { text: next.text }))
    
    return true
  }
  const applySkip = (decision: Extract<HookDecision, { kind: 'skip_tool' }>): void => {
    const chunks: string[] = []
    let current = ''
    for (const line of decision.note.split('\n')) {
      if (!line) continue
      if (/^(GUIDANCE|EVIDENCE|CONSTRAINT|OBSERVATION|STEP):/.test(line)) {
        if (current) chunks.push(current)
        current = line
      } else {
        current = current ? `${current} ${line}` : line
      }
    }
    if (current) chunks.push(current)
    for (const chunk of chunks) ctx.recordNote(chunk)
    if (decision.privacy) {
      ctx.emit(
        ctx.createRecord('run.error', {
          message: decision.privacy.hint,
          code: decision.privacy.code,
          tool: decision.privacy.tool,
        })
      )
      return
    }
    if (decision.blockedAsk) {
      ctx.emit(
        ctx.createRecord('run.error', {
          message: `ask_user blocked: ${decision.blockedAsk.reason} — "${decision.blockedAsk.question}"`,
          code: 'ask_user_blocked',
        })
      )
      return
    }
    const call = ctx.toolCall
    if (!call) return
    if (decision.log) ctx.emit(ctx.createRecord('run.log', { message: decision.log }))
    if (decision.result) {
      ctx.emit(
        ctx.createRecord('tool.result', {
          tool: call.tool,
          arguments: call.arguments,
          ok: decision.result.ok,
          ...(decision.result.ok
            ? { data: decision.result.data }
            : { error: decision.result.error }),
        })
      )
    }
  }
  const hitlOutcome = async (
    question: string,
    stopOnCancel: boolean
  ): Promise<RunAgentResult | 'continue'> => {
    const hitl = await awaitHitl(question, stopOnCancel)
    if (hitl === 'stop') return finish(ctx, 'cancelled', question)
    if (hitl === 'park') return finish(ctx, 'ask_user', question)
    return 'continue'
  }

  let stopped: RunAgentResult | null = null
  try {
    const started = pipeline.onStart(ctx)
    if (started.kind === 'stop') {
      stopped = finish(ctx, started.status ?? 'error', started.result)
      pipeline.onStop(ctx, stopped)
      return stopped
    }

    while (true) {
      ensureAnchorTask(ctx)
      ctx.syncTaskContract()
      syncDeliverableFromTask(ctx)
      ctx.taskScope = resolveTaskScope(ctx.task)
      agent.hooks.resetTask()
      let deterministicResult: string | undefined
      resetTurnGates(ctx.gates)

      stopped = null
      deterministicResult = await pipeline.runTaskPreflight(ctx)

      if (!stopped) {
        if (deterministicResult) {
          ctx.emit(
            ctx.createRecord('run.mode', {
              mode: 'deterministic',
              detail: '当前页列表提取可直接由 DOM 工具完成，未调用模型。',
            })
          )
          ctx.emit(ctx.createRecord('run.result', { text: deterministicResult }))
          stopped = finish(ctx, 'done', deterministicResult)
        } else {
          stopped = await runModelTurns({
            agent,
            ctx,
            finish,
            budgetExceeded,
            noteUsage,
            injectSteering,
            hitlOutcome,
            applySkip,
          })
        }
      }

      if (
        stopped &&
        (stopped.status === 'done' || stopped.status === 'max_steps') &&
        maybeFollowUpNext(stopped.result ?? stopped.status)
      ) {
        continue
      }
      if (stopped) {
        pipeline.onStop(ctx, stopped)
        return stopped
      }
    }
  } catch (e) {
    if (isAbortError(e)) {
      stopped = finish(ctx, 'cancelled')
      pipeline.onStop(ctx, stopped)
      return stopped
    }
    throw e
  } finally {
    if (planes.network && agent.profile?.manageNetwork !== false) await planes.network.stop().catch(() => {})
  }
}

Agent.prototype.run = function (this: Agent) {
  return runPiAgentLoop(this)
}
