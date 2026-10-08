import type { ToolCall } from '@naviforge/shared'
import {
  HARD_DENY_ERROR_CODES,
  formatListOpenConstraint,
  hardDenyQuestion,
  isCspEvalError,
  privacyHintFor,
  sameFailureQuestion,
  type ListOpenHint,
} from './run-limits.js'
import type { RecoveryPlan } from './recovery.js'
import type { RunAgentResult } from './agent.js'
import { fillCopy, uiCopy } from './ui-copy.js'

/** Model-facing; CspSkipHook uses the same string. */
export const CSP_EXECUTE_JS_HINT =
  'GUIDANCE: execute_js blocked by page CSP on this URL; use snapshot/read_page or existing evidence — do not retry'

export type ChatCompletionLike = {
  content: string
  reasoning?: string
  toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>
}

/** Command the loop executes. ProtocolHook owns retry budget; this only parses. */
export type LoopCommand =
  | { kind: 'proceed'; decision: ModelDecision }
  | { kind: 'retry_turn'; plan: RecoveryPlan; hint: string }
  | { kind: 'stop'; plan: RecoveryPlan; result: string; status?: RunAgentResult['status'] }

/** Minimal internal representation of one native model decision. */
export type ModelDecision = { call: ToolCall; summary: string }

export const FETCH_TEXT_BATCH_MAX = 10

/** Collect HTTPS URLs from one or more fetch_text tool calls (network-free). */
export function collectFetchTextUrls(
  calls: ReadonlyArray<{ name: string; arguments: Record<string, unknown> }>
): string[] {
  const urls: string[] = []
  for (const call of calls) {
    if (call.name !== 'fetch_text') continue
    const single = call.arguments.url
    if (typeof single === 'string' && single.trim()) urls.push(single.trim())
    const batch = call.arguments.urls
    if (Array.isArray(batch)) {
      for (const item of batch) {
        if (typeof item === 'string' && item.trim()) urls.push(item.trim())
      }
    }
  }
  return [...new Set(urls)]
}

/** Merge parallel fetch_text calls into one batch tool call. */
export function coalesceFetchTextBatch(
  calls: ReadonlyArray<{ name: string; arguments: Record<string, unknown> }>,
  summary: string
): ModelDecision | null {
  if (!calls.length || !calls.every((call) => call.name === 'fetch_text')) return null
  const urls = collectFetchTextUrls(calls)
  if (!urls.length) return null
  const maxChars = calls.find((call) => typeof call.arguments.max_chars === 'number')?.arguments.max_chars
  return {
    call: {
      tool: 'fetch_text',
      arguments: {
        urls: urls.slice(0, FETCH_TEXT_BATCH_MAX),
        ...(typeof maxChars === 'number' ? { max_chars: maxChars } : {}),
      },
    },
    summary: summary.trim() || `fetch_text x${urls.length}`,
  }
}

/**
 * Detect a model turn that is a content-safety / policy refusal rather than a
 * protocol slip (model forgot to call a tool, malformed arguments, etc).
 * Generic lexical patterns across zh/en — this is not a site/domain rule, it
 * is about the *shape* of a refusal (model declines to assist, cites policy,
 * safety, legality, or harm to a protected group) regardless of what page or
 * task triggered it.
 *
 * Why this matters: ProtocolHook's job is to push the model to retry when it
 * forgets the "exactly one tool call" protocol. Retrying a safety refusal
 * with the same GUIDANCE text just produces the same refusal again (model
 * will not call `system_done`/`system_ask_user` either, since from the
 * model's perspective calling *any* tool for this request is the thing it is
 * refusing to do). The loop must stop and surface `blocked`, not spin to
 * `run.error` after burning the retry budget on an unwinnable retry.
 */
export function looksLikeSafetyRefusal(text: string): boolean {
  if (!text.trim()) return false
  const patterns = [
    /\bI can('|’)t\b.{0,80}\b(help|assist|provide|retrieve|extract)\b/i,
    /\bI (will not|won('|’)t|cannot|can not)\b.{0,80}\b(assist|help|provide)\b/i,
    /\b(sexually exploitative|non-consensual|csam|child sexual abuse)\b/i,
    /\bagainst (my|our) (guidelines|policy|policies)\b/i,
    /\bI('m| am) not able to (help|assist) with\b/i,
    /我(无法|不能|不会)(帮|协助|提供|继续)/,
    /涉及(未成年人|色情|违法|暴力|自杀|自伤)/,
    /违反(了)?(使用)?(政策|规范|准则)/,
    /不予(提供|配合|协助)/,
  ]
  return patterns.some((re) => re.test(text))
}

/** Require exactly one native function tool call; text is never executable. */
export function interpretTurn(completion: ChatCompletionLike): LoopCommand {
  const calls = completion.toolCalls ?? []
  if (calls.length > 1) {
    const batch = coalesceFetchTextBatch(
      calls,
      (completion.content || completion.reasoning || '').trim() || `fetch_text x${calls.length}`
    )
    if (batch) return { kind: 'proceed', decision: batch }
    return {
      kind: 'retry_turn',
      plan: {
        strategy: 'protocol_retry',
        retryable: true,
        diagnostic: `Invalid LLM completion: expected exactly one function tool call, received ${calls.length}.`,
      },
      hint: 'GUIDANCE: 每轮只能调用一个工具。多篇 raw URL 请一次 fetch_text({ urls: ["https://...", ...] })，最多 10 个；禁止一次返回多个 function call。',
    }
  }
  if (calls.length === 1) {
    if (!calls[0]!.name) {
      return {
        kind: 'retry_turn',
        plan: {
          strategy: 'protocol_retry',
          retryable: true,
          diagnostic: 'Invalid LLM completion: function tool call is missing a name',
        },
        hint: 'GUIDANCE: function tool call 必须包含工具名。必须恰好调用一个工具；最终答案用 system_done，提问用 system_ask_user。',
      }
    }
    return {
      kind: 'proceed',
      decision: {
        call: { tool: calls[0]!.name, arguments: calls[0]!.arguments },
        summary: (completion.content || completion.reasoning || calls[0]!.name).trim(),
      },
    }
  }
  const raw = (completion.content || completion.reasoning || '').trim()
  const clip = raw.slice(0, 180).replace(/\s+/g, ' ')
  return {
    kind: 'retry_turn',
    plan: {
      strategy: 'protocol_retry',
      retryable: true,
      diagnostic: clip
        ? `Invalid LLM completion: no function tool call (${clip})`
        : 'Invalid LLM completion: no function tool call',
    },
    hint: 'GUIDANCE: 上一轮没有 function tool call。必须恰好调用一个工具；最终答案用 system_done，提问用 system_ask_user。',
  }
}

export type ToolOutcome = {
  notes: string[]
  forceAsk?: string
  markCsp?: boolean
}

/**
 * After-tool policy. Ordered private handlers = Chain of Responsibility inside
 * one aggregate so agent.ts does not own fail-streak / hard-deny / CSP.
 */
export class ToolOutcomePolicy {
  private failKey = ''
  private failCount = 0

  constructor(private readonly sameFailureLimit: number) {}

  resetStreak(): void {
    this.failKey = ''
    this.failCount = 0
  }

  onFailure(input: {
    tool: string
    code: string
    message: string
    listHints: ListOpenHint[]
    locale?: string
  }): ToolOutcome {
    const notes: string[] = []
    if (input.tool === 'dom_navigate' && input.code === 'bad_args') {
      notes.push(
        'CONSTRAINT: FORBIDDEN empty dom_navigate {}. Required {"action":"url","url":"https://..."}; prefer dom_click on a list item to open a video.'
      )
      if (input.listHints.length) notes.push(formatListOpenConstraint(input.listHints))
    }
    if (HARD_DENY_ERROR_CODES.has(input.code)) {
      this.resetStreak()
      return {
        notes,
        forceAsk: hardDenyQuestion(
          input.tool,
          input.code,
          privacyHintFor(input.code, input.locale),
          input.locale
        ),
      }
    }
    if (input.code === 'csp_eval_blocked' || isCspEvalError(input.message)) {
      this.resetStreak()
      notes.push(CSP_EXECUTE_JS_HINT)
      return { notes, markCsp: true }
    }
    if (this.sameFailureLimit > 0) {
      const key = `${input.tool}\0${input.code}`
      this.failCount = key === this.failKey ? this.failCount + 1 : 1
      this.failKey = key
      if (this.failCount >= this.sameFailureLimit) {
        const question = sameFailureQuestion(input.tool, input.code, this.failCount, input.locale)
        this.resetStreak()
        return { notes, forceAsk: question }
      }
    }
    return { notes }
  }
}

export function transportAskQuestion(message: string, locale?: string): string {
  return fillCopy(uiCopy(locale).transportAsk, { message })
}
