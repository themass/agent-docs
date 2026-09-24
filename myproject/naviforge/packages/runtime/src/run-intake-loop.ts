import {
  MAX_INTAKE_ROUNDS,
  composeIntakeSystemPrompt,
  compileIntakeUserPrompt,
  formatIntakeConstraints,
  normalizeClarificationQuestions,
  parseIntakeAnswerJson,
  shouldSkipIntake,
  summarizeIntakeAsk,
  type IntakeMode,
  INTAKE_OPENAI_TOOLS,
} from '@naviforge/intake'

import type { Agent, AgentCtx } from './agent-ctx.js'
import type { RunAgentResult } from './agent.js'
import { chatCompletion } from './llm.js'
import { isAbortError } from './recovery.js'

export type IntakeLoopDeps = {
  agent: Agent
  ctx: AgentCtx
  mode: IntakeMode
  hitlOutcome: (question: string, stopOnCancel: boolean) => Promise<RunAgentResult | 'continue'>
}

function singleToolCall(completion: Awaited<ReturnType<typeof chatCompletion>>): {
  name: string
  arguments: Record<string, unknown>
} | null {
  const calls = completion.toolCalls
  if (!calls?.length) return null
  if (calls.length !== 1) return null
  const call = calls[0]
  if (!call?.name) return null
  return { name: call.name, arguments: call.arguments ?? {} }
}

/** Pre-execution clarification loop (DSH / DeerFlow-style intake). */
export async function runIntakeLoop(deps: IntakeLoopDeps): Promise<'continue' | RunAgentResult> {
  const { agent, ctx, mode, hitlOutcome } = deps
  if (shouldSkipIntake(ctx.task, mode)) return 'continue'

  const priorSystem = ctx.prompt.system
  const priorTools = ctx.tools
  ctx.metadata.runPhase = 'intake'
  ctx.prompt.system = composeIntakeSystemPrompt(priorSystem, mode)
  ctx.tools = INTAKE_OPENAI_TOOLS

  ctx.emit(
    ctx.createRecord('run.mode', {
      mode: 'model',
      detail: '需求评估：由模型判断是否需要向你提问。',
    })
  )

  const confirmed: string[] = []
  let round = 0

  try {
    for (; round < MAX_INTAKE_ROUNDS; round++) {
      agent.signal?.throwIfAborted()
      const user = compileIntakeUserPrompt(
        ctx.task,
        confirmed,
        ctx.prompt.thread
          ? { memory: ctx.prompt.thread.memory, conversation: ctx.prompt.thread.conversation }
          : undefined
      )
      let completion: Awaited<ReturnType<typeof chatCompletion>>
      try {
        completion = await chatCompletion(agent.llm, ctx.prompt.system, user, {
          signal: agent.signal,
          tools: ctx.tools,
        })
      } catch (error) {
        if (isAbortError(error)) throw error
        ctx.emit(ctx.createRecord('run.error', { message: (error as Error).message }))
        return { status: 'error', result: (error as Error).message, recordedActions: [], recoveries: [] }
      }

      const call = singleToolCall(completion)
      if (!call) {
        ctx.recordNote('GUIDANCE: intake requires system_clarify or system_begin_task')
        continue
      }

      if (call.name === 'system_begin_task') {
        const summary = typeof call.arguments.summary === 'string' ? call.arguments.summary.trim() : ''
        const assumptions = Array.isArray(call.arguments.assumptions)
          ? call.arguments.assumptions.filter((v): v is string => typeof v === 'string')
          : []
        ctx.emit(
          ctx.createRecord('intake.complete', {
            summary: summary || ctx.task,
            assumptions,
            roundCount: round,
          })
        )
        for (const line of confirmed) ctx.recordNote(line)
        if (summary) ctx.recordNote(`INTAKE SUMMARY: ${summary}`)
        break
      }

      if (call.name !== 'system_clarify') {
        ctx.recordNote(`GUIDANCE: unknown intake tool ${call.name}`)
        continue
      }

      const questions = normalizeClarificationQuestions(call.arguments.questions)
      if (!questions.length) {
        ctx.recordNote('GUIDANCE: system_clarify requires at least one question')
        continue
      }

      ctx.emit(
        ctx.createRecord('intake.question', {
          round,
          questions,
        })
      )

      const parked = await hitlOutcome(summarizeIntakeAsk(questions), true)
      if (parked !== 'continue') return parked

      const answerText = ctx.metadata.lastIntakeAnswer
      const answers = parseIntakeAnswerJson(typeof answerText === 'string' ? answerText : '')
      if (!answers) {
        ctx.recordNote('GUIDANCE: intake answer missing; retry clarify')
        continue
      }

      ctx.emit(
        ctx.createRecord('intake.answer', {
          round,
          questions,
          answers,
          freeText: typeof answers._freeText === 'string' ? answers._freeText : undefined,
        })
      )

      confirmed.push(...formatIntakeConstraints(questions, answers))
      delete ctx.metadata.lastIntakeAnswer
    }
  } finally {
    ctx.prompt.system = priorSystem
    ctx.tools = priorTools
    delete ctx.metadata.runPhase
  }

  return 'continue'
}

/** Attach structured intake answer before resuming intake loop. */
export function attachIntakeAnswer(ctx: AgentCtx, text: string): void {
  ctx.metadata.lastIntakeAnswer = text
  ctx.recordNote(`INTAKE ANSWER: ${text}`)
}
