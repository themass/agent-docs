import type { ToolResult } from '@naviforge/shared'

import type { RunAgentResult } from './agent.js'
import type { AgentCtx } from './agent-ctx.js'
import {
  CONTEXT_BUDGET_RATIOS,
  inputTokenRatio,
  l1ProjectionCap,
} from './context-budget.js'
import { estimatePromptTokens } from './context-compaction.js'
import { emitContextMetrics } from './emit-context-metrics.js'
import { buildToolCatalog } from './tool-catalog.js'
import {
  projectTraceRecords,
  promptWouldExceedInputLimit,
  estimateToolsTokens,
} from './working-set.js'
import type { RecoveryPlan } from './recovery.js'
import {
  interpretTurn,
  ToolOutcomePolicy,
  transportAskQuestion,
  type ModelDecision,
  type LoopCommand,
  type ToolOutcome,
} from './failure.js'

export type { LoopCommand, ToolOutcome }

/**
 * Decision a hook returns. The loop executes; hooks mutate `AgentCtx` and/or
 * return a command. No `next()` onion — first non-`continue` wins at that phase.
 */
export type HookDecision =
  | { kind: 'continue' }
  | {
      kind: 'skip_tool'
      note: string
      log?: string
      result?: ToolResult
      /** HITL question blocked by policy — loop emits `ask_user_blocked`. */
      blockedAsk?: { question: string; reason: string }
      privacy?: { tool: string; code: string; hint: string }
      stop?: boolean
      stopResult?: string
    }
  | { kind: 'ask_user'; question: string; plan?: RecoveryPlan }
  | { kind: 'stop'; result: string; status?: RunAgentResult['status'] }
  | { kind: 'retry_turn'; hint: string; plan?: RecoveryPlan }
  | { kind: 'replace_decision'; decision: ModelDecision }

export const CONTINUE: HookDecision = { kind: 'continue' }

/**
 * Named checkpoints around the loop (Pi AgentLoopConfig + MAF middleware layers +
 * Hermes pre/post LLM/tool, without Cordis/`next()`).
 *
 * Hooks may rewrite `ctx.prompt`, `ctx.tools`, `ctx.skills`, `ctx.messages`,
 * `ctx.toolCall.arguments`. They must not own Chrome / LLM I/O.
 */
export interface AgentHook {
  readonly name: string
  onStart?(ctx: AgentCtx): HookDecision | void
  onStop?(ctx: AgentCtx, result: RunAgentResult): void
  beforeStep?(ctx: AgentCtx): HookDecision | void
  afterStep?(ctx: AgentCtx): void
  beforeModel?(ctx: AgentCtx): HookDecision | void | Promise<HookDecision | void>
  afterModel?(ctx: AgentCtx): LoopCommand | void
  onModelError?(ctx: AgentCtx): HookDecision | void
  beforeTool?(ctx: AgentCtx): HookDecision | void
  afterTool?(ctx: AgentCtx): ToolOutcome | void
  /** Deterministic reads before the model loop; first non-empty result wins. */
  runTaskPreflight?(ctx: AgentCtx): Promise<string | undefined>
}

type DecisionPhase = 'onStart' | 'beforeStep' | 'onModelError' | 'beforeTool'

export class WorkingSetHook implements AgentHook {
  readonly name = 'working-set'

  onStart(ctx: AgentCtx): void {
    ctx.emit(ctx.createRecord('run.tools', { catalog: buildToolCatalog(ctx.tools) }))
    emitContextMetrics(ctx)
  }

  async beforeModel(ctx: AgentCtx): Promise<HookDecision> {
    const maxInput = ctx.agent.limits.maxInputTokens
    const take = (projectionCap: number): boolean => {
      const projected = projectTraceRecords(ctx.ledger.all(), {
        maxInputTokens: projectionCap,
        ownerRunId: ctx.runId,
      })
      ctx.messages = [projected.prompt]
      ctx.prompt.loadedSkillText = ctx.gates.loadedSkillBodies.length
        ? ctx.gates.loadedSkillBodies.join('\n---\n')
        : undefined
      ctx.prompt.user = ctx.compileUser()
      return projected.pressured
    }
    const ratio = () =>
      inputTokenRatio({
        system: ctx.prompt.system,
        user: ctx.prompt.user,
        tools: ctx.tools,
        maxInputTokens: maxInput,
      })
    const inputTokens = () =>
      estimatePromptTokens({
        system: ctx.prompt.system,
        user: ctx.prompt.user,
        tools: ctx.tools,
      })
    const over = () =>
      promptWouldExceedInputLimit({
        system: ctx.prompt.system,
        user: ctx.prompt.user,
        toolsTokens: estimateToolsTokens(ctx.tools),
        maxInputTokens: maxInput,
      })

    take(maxInput)
    let pressure = ratio() >= CONTEXT_BUDGET_RATIOS.soft
    if (ratio() >= CONTEXT_BUDGET_RATIOS.soft) {
      pressure = take(l1ProjectionCap(maxInput, ratio())) || pressure
    }
    emitContextMetrics(ctx, {
      pressured: pressure || ratio() >= CONTEXT_BUDGET_RATIOS.hard,
    })

    const priorPressure = Number(ctx.metadata.contextProjectionPressure ?? 0)
    ctx.metadata.contextProjectionPressure = pressure ? priorPressure + 1 : 0

    const lastCompaction = [...ctx.ledger.all()]
      .reverse()
      .find((record) => record.type === 'context.compaction')
    const recordsSinceCompaction = lastCompaction
      ? ctx.ledger.all().filter((record) => record.at > lastCompaction.at).length
      : ctx.ledger.all().length
    const shouldCompact =
      ratio() >= CONTEXT_BUDGET_RATIOS.hard ||
      over() ||
      Number(ctx.metadata.contextProjectionPressure) >= 2
    const compactAllowed = !lastCompaction || recordsSinceCompaction >= 6

    if (shouldCompact && compactAllowed) {
      try {
        const beforeTokens = inputTokens()
        const records = ctx.ledger.all()
        const compacted = await ctx.agent.contextCompactor.compact({
          records,
          constraints: projectTraceRecords(records, { maxInputTokens: 2_000, ownerRunId: ctx.runId }).items
            .filter((entry) => entry.kind === 'constraint')
            .map((entry) => entry.content),
          openWork: projectTraceRecords(records, { maxInputTokens: 2_000, ownerRunId: ctx.runId }).items
            .filter((entry) => entry.kind === 'error' || entry.kind === 'step')
            .slice(-6)
            .map((entry) => entry.content),
        })
        ctx.appendCompaction({
          summary: compacted.summary,
          coveredRecordIds: records.map((record) => record.id),
          coveredRange: records.length ? { from: records[0]!.id, to: records.at(-1)!.id } : undefined,
          preservedConstraints: compacted.preservedConstraints,
          openWork: compacted.openWork,
          tokenUsage: compacted.tokenUsage,
          mode: compacted.mode ?? 'deterministic',
        })
        ctx.emit(
          ctx.createRecord('run.recovery', {
            strategy: 'fold_context',
            diagnostic:
              compacted.mode === 'llm'
                ? `L2 LLM compaction covered ${records.length} audit records`
                : `L2 deterministic compaction covered ${records.length} audit records`,
          })
        )
        take(l1ProjectionCap(maxInput, ratio()))
        const afterTokens = inputTokens()
        emitContextMetrics(ctx, {
          pressured: ratio() >= CONTEXT_BUDGET_RATIOS.soft,
          compaction: {
            beforeTokens,
            afterTokens,
            coveredRecords: records.length,
          },
        })
      } catch {
        take(Math.min(maxInput, 512))
      }
    }
    if (ratio() >= CONTEXT_BUDGET_RATIOS.stop || over()) {
      return { kind: 'stop', result: 'Model input limit exceeded after deterministic context projection.', status: 'error' }
    }
    return CONTINUE
  }
}

export class ProtocolHook implements AgentHook {
  readonly name = 'protocol'
  private invalidCount = 0

  constructor(private readonly maxRetries = 1) {}

  afterModel(ctx: AgentCtx): LoopCommand {
    if (!ctx.completion) throw new Error('ProtocolHook.afterModel: missing completion')
    const command = interpretTurn(ctx.completion)
    if (command.kind === 'proceed') {
      this.invalidCount = 0
      return command
    }
    if (command.kind !== 'retry_turn') return command
    this.invalidCount += 1
    if (this.invalidCount > this.maxRetries) {
      return {
        kind: 'stop',
        plan: {
          strategy: 'protocol_error',
          retryable: false,
          diagnostic: `${command.plan.diagnostic} (${this.invalidCount}/${this.maxRetries + 1} invalid completions)`,
        },
        result: command.plan.diagnostic,
      }
    }
    return {
      ...command,
      plan: {
        ...command.plan,
        diagnostic: `${command.plan.diagnostic} (retry ${this.invalidCount}/${this.maxRetries + 1})`,
      },
    }
  }

  reset(): void {
    this.invalidCount = 0
  }
}

export class ToolOutcomeHook implements AgentHook {
  readonly name = 'tool-outcome'

  constructor(private readonly policy: ToolOutcomePolicy) {}

  afterTool(ctx: AgentCtx): ToolOutcome {
    const result = ctx.toolResult
    if (!result) return { notes: [] }
    if (result.ok) {
      this.policy.resetStreak()
      return { notes: [] }
    }
    return this.policy.onFailure({
      tool: ctx.toolCall?.tool ?? '',
      code: result.error.code,
      message: result.error.message,
      listHints: ctx.gates.lastListHints,
      locale: ctx.agent.opts.locale,
    })
  }

  resetStreak(): void {
    this.policy.resetStreak()
  }
}

export class ModelErrorHook implements AgentHook {
  readonly name = 'model-error'

  onModelError(ctx: AgentCtx): HookDecision {
    const diagnostic = String(ctx.metadata.modelError ?? 'model request failed')
    return { kind: 'ask_user', question: transportAskQuestion(diagnostic, ctx.agent.opts.locale) }
  }
}

export class HookPipeline {
  constructor(readonly hooks: readonly AgentHook[]) {}

  private firstDecision(phase: DecisionPhase, ctx: AgentCtx): HookDecision {
    for (const hook of this.hooks) {
      const fn = hook[phase]
      if (!fn) continue
      const out = fn.call(hook, ctx)
      if (out && out.kind !== 'continue') return out
    }
    return CONTINUE
  }

  onStart(ctx: AgentCtx): HookDecision {
    return this.firstDecision('onStart', ctx)
  }

  beforeStep(ctx: AgentCtx): HookDecision {
    return this.firstDecision('beforeStep', ctx)
  }

  async beforeModel(ctx: AgentCtx): Promise<HookDecision> {
    ctx.syncFromAgent()
    for (const hook of this.hooks) {
      const out = await hook.beforeModel?.(ctx)
      if (out && out.kind !== 'continue') return out
    }
    return CONTINUE
  }

  onModelError(ctx: AgentCtx): HookDecision {
    return this.firstDecision('onModelError', ctx)
  }

  beforeTool(ctx: AgentCtx): HookDecision {
    return this.firstDecision('beforeTool', ctx)
  }

  afterModel(ctx: AgentCtx): LoopCommand {
    let last: LoopCommand | null = null
    for (const hook of this.hooks) {
      if (!hook.afterModel) continue
      const cmd = hook.afterModel(ctx)
      if (!cmd) continue
      last = cmd
      if (cmd.kind === 'proceed') ctx.decision = cmd.decision
      if (cmd.kind !== 'proceed') return cmd
    }
    if (!last) throw new Error('HookPipeline.afterModel: no protocol hook registered')
    return last
  }

  afterTool(ctx: AgentCtx): ToolOutcome {
    let merged: ToolOutcome = { notes: [] }
    for (const hook of this.hooks) {
      if (!hook.afterTool) continue
      const out = hook.afterTool(ctx)
      if (!out) continue
      merged = {
        notes: [...merged.notes, ...out.notes],
        forceAsk: out.forceAsk ?? merged.forceAsk,
        markCsp: merged.markCsp || out.markCsp,
      }
    }
    return merged
  }

  /** New task / HITL resume: protocol hint budget and same-failure streak. */
  resetTask(): void {
    for (const hook of this.hooks) {
      if (hook instanceof ProtocolHook) hook.reset()
      if (hook instanceof ToolOutcomeHook) hook.resetStreak()
    }
  }

  afterStep(ctx: AgentCtx): void {
    for (const hook of this.hooks) hook.afterStep?.(ctx)
  }

  onStop(ctx: AgentCtx, result: RunAgentResult): void {
    for (const hook of this.hooks) hook.onStop?.(ctx, result)
  }

  async runTaskPreflight(ctx: AgentCtx): Promise<string | undefined> {
    for (const hook of this.hooks) {
      const result = await hook.runTaskPreflight?.(ctx)
      if (result) return result
    }
    return undefined
  }
}
