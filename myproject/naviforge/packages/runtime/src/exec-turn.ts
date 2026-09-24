import type { DomPlane, DomSnapshot, SnapshotMode } from '@naviforge/dom-plane'
import type { ToolCall, ToolResult } from '@naviforge/shared'
import { isMcpQualifiedToolName } from '@naviforge/shared'
import { detectUrlDrift, evaluateAskUser, isUrlMutatingTool } from '@naviforge/policy'
import type { RecordedDomAction } from '@naviforge/playbook'
import type { TraceRecord } from '@naviforge/session'

import type { AgentIo } from './agent-ctx.js'
import type { ModelDecision } from './failure.js'
import { classifyFailure, type RecoveryPlan } from './recovery.js'
import { resolveMcpCall } from './mcp-tools.js'
import { privacyHintFor, isCspEvalError } from './run-limits.js'
import { executeBuiltinTool } from './tools/builtin-handlers.js'
import {
  formatExtractContentTrace,
  formatExtractDomTrace,
  formatReadPageTrace,
  formatToolTrace,
  READ_PAGE_TRACE_CHARS,
} from './tools/format-tool-trace.js'

export { isCspEvalError }
export {
  formatExtractContentTrace,
  formatExtractDomTrace,
  formatReadPageTrace,
  formatToolTrace,
  READ_PAGE_TRACE_CHARS,
}

function str(v: unknown): string | null {
  return typeof v === 'string' ? v : null
}

export function normalizeScrollArgs(
  args: Record<string, unknown>
): { to?: 'top' | 'bottom' | 'y'; y?: number; direction?: 'up' | 'down'; amount?: number } {
  const toRaw = str(args.to)
  const y = typeof args.y === 'number' && Number.isFinite(args.y) ? args.y : null
  const direction = str(args.direction)
  const amount = typeof args.amount === 'number' && Number.isFinite(args.amount) ? args.amount : null
  if (toRaw === 'top' || toRaw === 'bottom') return { to: toRaw }
  if (toRaw === 'y' && y != null) return { to: 'y', y }
  if (y != null) return { y }
  if (direction === 'up' || direction === 'down') {
    return { direction, amount: amount ?? undefined }
  }
  return { direction: 'down' }
}

export function parseSnapshotMode(value: unknown): SnapshotMode | undefined {
  return value === 'compact' || value === 'viewport' || value === 'full' ? value : undefined
}

export async function snapshotWithRetry(dom: DomPlane): Promise<ToolResult<DomSnapshot>> {
  const first = await dom.snapshot()
  if (first.ok) return first
  await new Promise((resolve) => setTimeout(resolve, 400))
  return dom.snapshot()
}

type ExecOut = {
  nextSnap: DomSnapshot
  trace: string
  recorded?: RecordedDomAction
  terminal?: TraceRecord
  recovery?: RecoveryPlan
  toolResult?: TraceRecord
}

/** Host meta-tools — always available even under Skill hard allowlist. */
export function isToolAllowed(tool: string, allowedTools?: ReadonlySet<string>): boolean {
  return (
    !allowedTools ||
    tool.startsWith('system_') ||
    tool.startsWith('workspace_') ||
    tool === 'workspace' ||
    tool === 'network_read' ||
    (tool.startsWith('network_') && tool !== 'network_intercept' && tool !== 'network_clear_intercepts') ||
    tool === 'skill_load' ||
    isMcpQualifiedToolName(tool) ||
    allowedTools.has(tool)
  )
}

export async function executeQualifiedTool(
  decision: ModelDecision,
  action: ToolCall,
  ctx: AgentIo,
  snap: DomSnapshot,
  blockAsk: (question: string) => ExecOut | null
): Promise<
  | { kind: 'builtin'; out: ExecOut }
  | { kind: 'result'; result: ToolResult; snap: DomSnapshot; recorded?: RecordedDomAction }
> {
  if (isMcpQualifiedToolName(action.tool)) {
    if (!ctx.callMcpTool) {
      return {
        kind: 'result',
        result: {
          ok: false,
          error: { code: 'no_mcp', message: 'MCP Host is unavailable', recoverable: false },
        },
        snap,
      }
    }
    const resolved = resolveMcpCall(action.tool, action.arguments, ctx.mcpTools)
    if (!resolved.ok) {
      return {
        kind: 'result',
        result: {
          ok: false,
          error: { code: 'bad_args', message: resolved.message, recoverable: true },
        },
        snap,
      }
    }
    const result = await ctx.callMcpTool(
      resolved.call.serverId,
      resolved.call.tool,
      resolved.call.arguments
    )
    return { kind: 'result', result, snap }
  }

  const builtin = await executeBuiltinTool({ decision, action, ctx, snap, blockAsk })
  if ('result' in builtin) {
    return {
      kind: 'result',
      result: builtin.result,
      snap: builtin.snap,
      recorded: builtin.recorded,
    }
  }
  return { kind: 'builtin', out: builtin }
}

export async function execTurn(decision: ModelDecision, ctx: AgentIo): Promise<ExecOut> {
  const { planes: { dom }, taskScope } = ctx
  let snap = ctx.snap
  const action = decision.call

  const blockAsk = (question: string): ExecOut | null => {
    const decision = evaluateAskUser(question, taskScope, ctx.hitlPolicy)
    if (decision.allow) return null
    ctx.emit?.(
      ctx.createRecord('run.error', {
        message: `ask_user blocked: ${decision.reason} — "${question}"`,
        code: 'ask_user_blocked',
      })
    )
    return {
      nextSnap: snap,
      trace: `ask_user blocked: ${decision.reason} — "${question}"`,
    }
  }

  if (action.tool === 'system_done') {
    const result = str(action.arguments.result)
    if (!result?.trim()) {
      return {
        nextSnap: snap,
        trace: 'invalid system_done: missing result',
        terminal: ctx.createRecord('run.error', { message: 'system_done requires a non-empty result.' }),
      }
    }
    return { nextSnap: snap, trace: `done: ${result}`, terminal: ctx.createRecord('run.result', { text: result }) }
  }
  if (action.tool === 'system_ask_user') {
    const q = str(action.arguments.question)
    if (!q?.trim()) {
      return {
        nextSnap: snap,
        trace: 'invalid system_ask_user: missing question',
        terminal: ctx.createRecord('run.error', { message: 'system_ask_user requires a non-empty question.' }),
      }
    }
    const blocked = blockAsk(q)
    if (blocked) return blocked
    return {
      nextSnap: snap,
      trace: `ask: ${q}`,
      terminal: ctx.createRecord('run.ask', { question: q, wait: 'user' }),
    }
  }

  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  const urlBefore = snap.url

  const dispatched = await executeQualifiedTool(decision, action, ctx, snap, blockAsk)
  if (dispatched.kind === 'builtin') return dispatched.out
  result = dispatched.result
  snap = dispatched.snap
  recorded = dispatched.recorded

  if (!result.ok) {
    const hint = privacyHintFor(result.error.code, ctx.locale)
    if (hint) {
      ctx.emit?.(
        ctx.createRecord('run.error', {
          message: hint,
          code: result.error.code,
          tool: action.tool,
        })
      )
    }
  }

  let nextSnap = snap
  if (action.tool === 'dom_snapshot' && result.ok) {
    nextSnap = result.data as DomSnapshot
  } else {
    const refreshed = await dom.snapshot()
    if (refreshed.ok) nextSnap = refreshed.data
  }

  let trace = result.ok
    ? formatToolTrace(action.tool, result.data, action.arguments)
    : `${action.tool} fail ${result.error.message}`

  if (result.ok && isUrlMutatingTool(action.tool)) {
    const drift = detectUrlDrift(urlBefore, nextSnap.url, taskScope)
    if (drift.drifted) {
      const driftedTo = nextSnap.url
      let rolledBack = false
      if (ctx.rollbackUrlDrift && dom.navigate) {
        const back = await dom.navigate('back')
        if (back.ok) {
          const afterBack = await dom.snapshot()
          if (afterBack.ok) {
            nextSnap = afterBack.data
            rolledBack = true
          }
        }
      }
      ctx.emit?.(
        ctx.createRecord('run.recovery', {
          strategy: 'scope_violation',
          diagnostic: rolledBack ? `${drift.message} (rolled back)` : drift.message,
          from: urlBefore,
          to: driftedTo,
        })
      )
      trace = rolledBack
        ? `url_drift blocked: ${drift.message} — history.back() applied; use highlight/scroll on this page`
        : `url_drift blocked: ${drift.message} — fresh snapshot attached; use highlight/scroll on this page`
    }
  }

  return {
    nextSnap,
    trace,
    recorded,
    recovery: result.ok ? undefined : classifyFailure(result.error),
    toolResult: ctx.createRecord('tool.result', {
      tool: action.tool,
      arguments: action.arguments,
      ok: result.ok,
      ...(result.ok
        ? { data: result.data }
        : { error: result.error }),
    }),
  }
}
