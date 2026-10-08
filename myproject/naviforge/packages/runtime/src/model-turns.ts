import type { Agent, AgentCtx } from './agent-ctx.js'
import type { RunAgentResult } from './agent.js'
import { formatActingDetail } from './acting-detail.js'
import type { HookDecision } from './hooks.js'
import { chatCompletion } from './llm.js'
import type { ModelDecision } from './failure.js'
import { transportAskQuestion } from './failure.js'
import { isAbortError, retry } from './recovery.js'
import { execTurn } from './exec-turn.js'
import { applyPageSignalsToCtx } from './page-signals-hydrate.js'
import { PI_LOOP_NOTE, prepareNextTurn } from './pi-run-loop.js'
import { applyPageFrictionToCtx, shouldRefreshPageFriction } from './page-friction/index.js'
import { resolveTaskMode } from './task-classifier.js'

function decisionStatus(decision: ModelDecision): 'act' | 'done' | 'ask_user' {
  if (decision.call.tool === 'system_done') return 'done'
  if (decision.call.tool === 'system_ask_user') return 'ask_user'
  return 'act'
}

function decisionSummary(
  decision: ModelDecision,
  completion: { content: string; reasoning?: string }
): string {
  const visible =
    decision.call.tool === 'system_done'
      ? decision.call.arguments.result
      : decision.call.tool === 'system_ask_user'
        ? decision.call.arguments.question
        : completion.content || completion.reasoning
  return typeof visible === 'string' && visible.trim() ? visible : decision.call.tool
}

export type ModelTurnsDeps = {
  agent: Agent
  ctx: AgentCtx
  finish: (ctx: AgentCtx, status: RunAgentResult['status'], result?: string) => RunAgentResult
  budgetExceeded: () => string | null
  noteUsage: (usage?: { promptTokens: number; completionTokens: number; totalTokens: number }) => void
  injectSteering: () => void
  hitlOutcome: (question: string, stopOnCancel: boolean) => Promise<RunAgentResult | 'continue'>
  applySkip: (decision: Extract<HookDecision, { kind: 'skip_tool' }>) => void
}

/** Inner Pi loop: prepareNextTurn → steering → one model tool (one task scope). */
export async function runModelTurns(deps: ModelTurnsDeps): Promise<RunAgentResult | null> {
  const {
    agent,
    ctx,
    finish,
    budgetExceeded,
    noteUsage,
    injectSteering,
    hitlOutcome,
    applySkip,
  } = deps
  const opts = agent.opts
  const planes = agent.planes
  const pipeline = agent.hooks
  let stepsUsed = 0
  let modelModeAnnounced = false
  let stopped: RunAgentResult | null = null
  ctx.recordNote(PI_LOOP_NOTE)

  for (; stepsUsed < agent.limits.maxSteps; stepsUsed++) {
    ctx.turnIndex = stepsUsed
    await prepareNextTurn(ctx)
    agent.signal?.throwIfAborted()
    const overBudget = budgetExceeded()
    if (overBudget) {
      ctx.emit(ctx.createRecord('run.error', { message: overBudget }))
      stopped = finish(ctx, 'error', overBudget)
      break
    }
    if (agent.pause?.isPaused()) {
      ctx.emit(ctx.createRecord('run.note', { text: 'paused', topic: 'pause' }))
      await agent.pause.waitIfPaused(agent.signal)
      ctx.emit(ctx.createRecord('run.note', { text: 'resumed', topic: 'resume' }))
    }
    agent.signal?.throwIfAborted()
    injectSteering()

    const stepGate = pipeline.beforeStep(ctx)
    if (stepGate.kind === 'stop') {
      stopped = finish(ctx, stepGate.status ?? 'error', stepGate.result)
      break
    }
    if (stepGate.kind === 'ask_user') {
      const parked = await hitlOutcome(stepGate.question, true)
      if (parked !== 'continue') {
        stopped = parked
        break
      }
      continue
    }

    if (!modelModeAnnounced) {
      ctx.emit(
        ctx.createRecord('run.mode', {
          mode: 'model',
          detail: 'Pi runLoop：prepareNextTurn 注入 PAGE STATE，再执行一个工具。',
        })
      )
      modelModeAnnounced = true
    }

    ctx.imageDataUrl = undefined
    if (agent.vision) {
      if (ctx.visionShot.dataUrl) {
        ctx.imageDataUrl = ctx.visionShot.dataUrl
      } else if (planes.dom.screenshot) {
        const shot = await planes.dom.screenshot()
        if (shot.ok) {
          ctx.visionShot.dataUrl = shot.data.dataUrl
          ctx.imageDataUrl = shot.data.dataUrl
          if (planes.workspace) {
            void planes.workspace
              .saveShot({
                kind: 'vision',
                dataUrl: shot.data.dataUrl,
                threadId: opts.workspaceThread?.threadId,
                slug: opts.workspaceThread?.slug,
                title: opts.workspaceThread?.title,
                runId: opts.workspaceThread?.runId,
                tool: 'vision',
              })
              .catch(() => {})
          }
        }
      }
    }
    await ctx.refreshNetwork()
    const prepared = await pipeline.beforeModel(ctx)
    if (prepared.kind === 'stop') {
      stopped = finish(ctx, prepared.status ?? 'error', budgetExceeded() ?? prepared.result)
      break
    }
    const user = ctx.prompt.user
    let decision: ModelDecision
    let completionIo: {
      content: string
      reasoning?: string
      toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>
    } = { content: '' }
    try {
      const completion = await retry(
        () =>
          chatCompletion(agent.llm, ctx.prompt.system, user, {
            signal: agent.signal,
            imageDataUrl: ctx.imageDataUrl,
            tools: ctx.tools,
          }),
        {
          attempts: 2,
          delayMs: 300,
          signal: agent.signal,
          onRetry: (attempt, error) => {
            ctx.recover({
              strategy: 'retry_request',
              retryable: true,
              diagnostic: `Model request retry ${attempt}: ${(error as Error).message}`,
            })
          },
        }
      )
      noteUsage(completion.usage)
      completionIo = completion
      ctx.completion = completion
      const command = pipeline.afterModel(ctx)
      if ('plan' in command && command.plan) ctx.recover(command.plan)
      if (command.kind !== 'proceed') {
        ctx.emit(
          ctx.createRecord('model.turn', {
            status: 'act',
            summary:
              ('plan' in command ? command.plan?.diagnostic.slice(0, 80) : undefined) ?? command.kind,
            io: {
              user,
              assistant: completionIo.content,
              reasoning: completionIo.reasoning,
              toolCalls: completionIo.toolCalls,
              hasImage: Boolean(ctx.imageDataUrl),
            },
          })
        )
      }
      if (command.kind === 'retry_turn') {
        ctx.recordNote(command.hint)
        pipeline.afterStep(ctx)
        continue
      }
      if (command.kind === 'stop') {
        stopped = finish(ctx, command.status ?? 'error', command.result)
        break
      }
      decision = command.decision
    } catch (error) {
      if (isAbortError(error)) throw error
      const diagnostic = (error as Error).message
      ctx.metadata.modelError = diagnostic
      ctx.recover({
        strategy: 'ask_user',
        retryable: false,
        diagnostic,
      })
      const errDecision = pipeline.onModelError(ctx)
      if (errDecision.kind === 'stop') {
        stopped = finish(ctx, errDecision.status ?? 'error', errDecision.result)
        break
      }
      const question =
        errDecision.kind === 'ask_user' ? errDecision.question : transportAskQuestion(diagnostic)
      const parked = await hitlOutcome(question, true)
      if (parked !== 'continue') {
        if (parked.status === 'cancelled') parked.result = diagnostic
        stopped = parked
        break
      }
      pipeline.afterStep(ctx)
      continue
    }

    ctx.emit(
      ctx.createRecord('model.turn', {
        status: decisionStatus(decision),
        summary: decisionSummary(decision, completionIo),
        call: { tool: decision.call.tool, arguments: decision.call.arguments },
        io: {
          user,
          assistant: completionIo.content,
          reasoning: completionIo.reasoning,
          toolCalls: completionIo.toolCalls,
          hasImage: Boolean(ctx.imageDataUrl),
        },
      })
    )

    const steerNow = agent.queue?.drainSteering() ?? []
    if (steerNow.length) {
      for (const text of steerNow) {
        ctx.recordNote(
          `USER CORRECTION: USER CORRECTION (obey over prior plan; abandon pending tool): ${text}`
        )
      }
      ctx.emit(ctx.createRecord('user.steer', { texts: steerNow, phase: 'abort_tool' }))
      pipeline.afterStep(ctx)
      continue
    }

    ctx.emit(
      ctx.createRecord('run.note', {
        text: formatActingDetail(decision.call.tool, decision.call.arguments, agent.opts.locale),
        topic: 'status',
      })
    )
    ctx.decision = decision
    ctx.bindToolCall(decision)
    if (decisionStatus(decision) === 'act') {
      const gate = pipeline.beforeTool(ctx)
      if (gate.kind === 'skip_tool') {
        applySkip(gate)
        if (gate.stop) {
          const result = gate.stopResult ?? gate.note
          ctx.emit(ctx.createRecord('run.result', { text: result }))
          stopped = finish(ctx, 'done', result)
          break
        }
        pipeline.afterStep(ctx)
        continue
      }
      if (gate.kind === 'ask_user') {
        const parked = await hitlOutcome(gate.question, false)
        if (parked !== 'continue') {
          stopped = parked
          break
        }
        pipeline.afterStep(ctx)
        continue
      }
      if (gate.kind === 'stop') {
        stopped = finish(ctx, gate.status ?? 'error', gate.result)
        break
      }
      if (gate.kind === 'replace_decision') {
        decision = gate.decision
        ctx.decision = decision
        ctx.bindToolCall(decision)
      }
      ctx.applyToolArgs()
      decision = ctx.decision ?? decision
    }

    const urlBeforeSnap = ctx.snap.url
    const { nextSnap, trace, terminal, recorded, recovery, toolResult } = await execTurn(
      decision,
      ctx.io()
    )
    if (toolResult) ctx.emit(toolResult)
    if (recorded) ctx.recordedActions.push(recorded)
    if (recovery) ctx.recover(recovery)
    ctx.toolResult =
      toolResult?.type === 'tool.result'
        ? toolResult.payload.ok
          ? { ok: true, data: toolResult.payload.data }
          : {
              ok: false,
              error: {
                ...toolResult.payload.error!,
                recoverable: toolResult.payload.error?.recoverable ?? false,
              },
            }
        : undefined
    ctx.toolTrace = trace

    let forceAsk: string | null = null
    if (toolResult) {
      const outcome = pipeline.afterTool(ctx)
      for (const line of outcome.notes) ctx.recordNote(line)
      if (outcome.markCsp) ctx.gates.jsCspBlocked.add(ctx.snap.url)
      forceAsk = outcome.forceAsk ?? null
    }

    ctx.emit(ctx.createRecord('run.log', { message: trace }))
    ctx.snap = nextSnap
    const toolName = decision.call.tool
    if (
      nextSnap.url !== urlBeforeSnap &&
      resolveTaskMode(ctx.task) === 'in_page' &&
      ctx.agent.planes.dom.collectPageSignalRaw
    ) {
      await applyPageSignalsToCtx(ctx, { url: nextSnap.url })
    }
    const executed = ctx.toolResult
    if (executed?.ok && shouldRefreshPageFriction(toolName)) {
      const bodyText =
        toolName === 'dom_read' &&
        executed.data &&
        typeof executed.data === 'object' &&
        typeof (executed.data as { text?: unknown }).text === 'string'
          ? (executed.data as { text: string }).text
          : undefined
      const friction = await applyPageFrictionToCtx(ctx, {
        tool: toolName,
        bodyText,
        skipJs: !ctx.agent.policy.allowDomInject,
      })
      if (!forceAsk && friction.forceAsk) forceAsk = friction.forceAsk
      if (friction.report?.kinds.includes('rate_limit')) {
        ctx.recordNote('CONSTRAINT: rate_limit detected — navigation backoff active')
      }
    }
    await opts.saveCheckpoint?.(stepsUsed, decisionSummary(decision, completionIo))
    injectSteering()

    if (forceAsk) {
      const parked = await hitlOutcome(forceAsk, true)
      if (parked !== 'continue') {
        stopped = parked
        break
      }
      injectSteering()
      pipeline.afterStep(ctx)
      continue
    }

    if (terminal) {
      if (terminal.type === 'run.ask') {
        const parked = await hitlOutcome(terminal.payload.question, false)
        if (parked === 'continue') {
          injectSteering()
          pipeline.afterStep(ctx)
          continue
        }
        stopped = parked
        break
      }
      ctx.emit(terminal)
      if (terminal.type === 'run.result') {
        stopped = finish(ctx, 'done', terminal.payload.text)
        break
      }
      stopped = finish(
        ctx,
        'error',
        terminal.type === 'run.error' ? terminal.payload.message : 'error'
      )
      break
    }
    pipeline.afterStep(ctx)
  }

  if (!stopped) {
    ctx.turnIndex = undefined
    const reason = JSON.stringify({
      code: 'max_steps',
      steps: agent.limits.maxSteps,
      lastTrace: ctx.ledger.at(-1) ?? '(no action completed)',
      finalUrl: ctx.snap.url,
      nextStep: 'Clarify the task or run again from the current page.',
    })
    ctx.emit(ctx.createRecord('run.error', { message: reason, code: 'blocked' }))
    stopped = finish(ctx, 'max_steps', reason)
  }

  return stopped
}
