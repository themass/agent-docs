import type { DomPlane } from '@naviforge/dom-plane'
import type { TabsPlane } from './tabs-plane.js'
import { createTraceRecord } from '@naviforge/session'

import type {
  AgentOptions,
  ExternalMcpTool,
  RunAgentResult,
} from './agent.js'
import { composeSystemPrompt } from './prompt.js'
import { isAbortError } from './recovery.js'
import type { SearchPlane } from './search-plane.js'
import type { FetchPlane } from './fetch-plane.js'
import type { NetworkPlane } from '@naviforge/network-plane'
import type { LlmConfig } from './llm.js'
import { readonlyDom } from './leaf-planes.js'
import { READONLY_RUN_PROFILE } from './run-profile.js'
import { MAX_PARALLEL_SUBTASKS, normalizeSpawnBriefs } from './subtask-guidance.js'

type LeafSessionStatus = 'success' | 'failed' | 'cancelled'

export type ReadonlySubAgentOptions = {
  briefs: string[]
  parentRunId: string
  parentSessionId?: string
  anchorTabId?: number
  dom: DomPlane
  llm: LlmConfig
  network?: NetworkPlane
  mcpTools?: ExternalMcpTool[]
  callMcpTool?: AgentOptions['callMcpTool']
  search?: SearchPlane
  fetch?: FetchPlane
  signal?: AbortSignal
  maxSteps?: number
  /** Audit sink for leaf runs — never forwarded to the parent ledger. */
  onLeafRecord?: AgentOptions['onLeafRecord']
  onLeafSessionStart?: AgentOptions['onLeafSessionStart']
  onLeafSessionComplete?: AgentOptions['onLeafSessionComplete']
  createLeafPlanes?: AgentOptions['createLeafPlanes']
  onTokenUsage?: AgentOptions['onTokenUsage']
}

export type ReadonlyChildResult = {
  runId: string
  parentRunId: string
  status: RunAgentResult['status']
  result?: string
}

export type ReadonlyBatchResult = {
  children: ReadonlyChildResult[]
}

function leafSessionStatus(status: RunAgentResult['status']): LeafSessionStatus {
  if (status === 'cancelled') return 'cancelled'
  if (status === 'done') return 'success'
  return 'failed'
}

/**
 * Run up to three independent readonly leaves through the canonical Agent pipeline.
 * Each leaf owns its own trace sink and optional ephemeral tab scope; the parent
 * only receives the structured batch tool result.
 */
export async function runReadonlySubAgents(opts: ReadonlySubAgentOptions): Promise<ReadonlyBatchResult> {
  if (!opts.briefs.length || opts.briefs.length > MAX_PARALLEL_SUBTASKS) {
    throw new Error(`briefs must contain 1-${MAX_PARALLEL_SUBTASKS} items`)
  }
  if (opts.briefs.some((brief) => !brief.trim())) throw new Error('briefs must not contain empty items')

  const { Agent } = await import('./agent.js')
  const anchorTabId = opts.anchorTabId ?? 0

  const children = await Promise.all(
    opts.briefs.map(async (brief, index) => {
      const runId = crypto.randomUUID()
      await opts.onLeafSessionStart?.({ childRunId: runId, brief, index })
      const leafBundle = opts.createLeafPlanes
        ? await opts.createLeafPlanes({ childRunId: runId, anchorTabId })
        : undefined
      const emitLeaf = (record: Parameters<NonNullable<AgentOptions['onLeafRecord']>>[0]) => {
        opts.onLeafRecord?.(record)
      }
      emitLeaf(
        createTraceRecord({
          type: 'run.context',
          runId,
          parentRunId: opts.parentRunId,
          payload: {
            systemPrompt: composeSystemPrompt(undefined, {
              hasMcpTools: Boolean(opts.mcpTools?.some((t) => t.readonly)),
              runProfile: 'readonly-child',
            }),
            tools: [
              ...READONLY_RUN_PROFILE.allowedTools,
              ...(opts.mcpTools ?? [])
                .filter((tool) => tool.readonly)
                .map((tool) => `mcp__${tool.serverId}__${tool.name}`),
            ],
          },
        })
      )
      const agent = new Agent({
        task: brief,
        runId,
        parentRunId: opts.parentRunId,
        parentSessionId: opts.parentSessionId,
        dom: readonlyDom(leafBundle?.dom ?? opts.dom),
        tabs: leafBundle?.tabs,
        llm: opts.llm,
        network: opts.network,
        mcpTools: opts.mcpTools,
        callMcpTool: opts.callMcpTool,
        search: opts.search,
        fetch: opts.fetch,
        signal: opts.signal,
        maxSteps: opts.maxSteps ?? 16,
        runProfile: READONLY_RUN_PROFILE,
        onRecord: emitLeaf,
        onTokenUsage: opts.onTokenUsage,
      })
      return { runId, agent, brief, index, leafBundle }
    })
  )

  const results = await Promise.allSettled(
    children.map(async ({ runId, agent, leafBundle }): Promise<ReadonlyChildResult> => {
      try {
        const result = await agent.run()
        opts.onLeafSessionComplete?.({ childRunId: runId, status: leafSessionStatus(result.status) })
        return { runId, parentRunId: opts.parentRunId, status: result.status, result: result.result }
      } finally {
        await leafBundle?.dispose().catch(() => {})
      }
    })
  )
  if (opts.signal?.aborted) opts.signal.throwIfAborted()

  return {
    children: results.map((outcome, index): ReadonlyChildResult => {
      if (outcome.status === 'fulfilled') return outcome.value
      const child = children[index]!
      const error = outcome.reason
      const message = error instanceof Error ? error.message : String(error)
      const status = isAbortError(error) ? 'cancelled' : 'error'
      opts.onLeafRecord?.(
        createTraceRecord({
          type: 'run.error',
          runId: child.runId,
          parentRunId: opts.parentRunId,
          payload: { message, code: status === 'cancelled' ? 'cancelled' : 'child_error' },
        })
      )
      opts.onLeafSessionComplete?.({
        childRunId: child.runId,
        status: status === 'cancelled' ? 'cancelled' : 'failed',
      })
      return { runId: child.runId, parentRunId: opts.parentRunId, status, result: message }
    }),
  }
}
