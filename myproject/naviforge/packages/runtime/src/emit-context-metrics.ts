import { buildContextBreakdown, type ContextCompactionMetric } from '@naviforge/context-metrics'

import type { AgentCtx } from './agent-ctx.js'
import {
  consolidateUserPromptMetricBlocks,
  CONTEXT_METRIC_LABELS,
  toolsMetricText,
} from './context-metrics-blocks.js'
import { compileUserPromptBlocks, KERNEL_PROMPT } from './prompt.js'

export function emitContextMetrics(
  ctx: AgentCtx,
  opts?: { pressured?: boolean; compaction?: ContextCompactionMetric }
): void {
  const rawBlocks = compileUserPromptBlocks(
    ctx.task,
    ctx.snap,
    ctx.messages,
    ctx.networkText,
    ctx.prompt.loadedSkillText,
    ctx.prompt.thread,
    ctx.agent.opts.locale
  )

  const systemBlocks = [
    {
      id: 'system',
      label: CONTEXT_METRIC_LABELS.system,
      // Kernel only — skill catalog is a separate block so totals are not double-counted.
      text: KERNEL_PROMPT,
    },
  ]
  const skillCatalog = ctx.agent.skillGuidance?.trim()
  if (skillCatalog) {
    systemBlocks.push({
      id: 'skill_catalog',
      label: CONTEXT_METRIC_LABELS.skill_catalog,
      text: skillCatalog,
    })
  }
  const builtinTools = ctx.tools.filter((tool) => !tool.function.name.startsWith('mcp__'))
  const mcpTools = ctx.tools.filter((tool) => tool.function.name.startsWith('mcp__'))
  systemBlocks.push({
    id: 'tools',
    label: CONTEXT_METRIC_LABELS.tools,
    text: toolsMetricText(builtinTools),
  })
  systemBlocks.push({
    id: 'mcp_tools',
    label: CONTEXT_METRIC_LABELS.mcp_tools,
    text: mcpTools.length ? toolsMetricText(mcpTools) : '',
  })

  const breakdown = buildContextBreakdown({
    systemBlocks,
    blocks: consolidateUserPromptMetricBlocks(rawBlocks),
    limitInputTokens: ctx.agent.limits.maxInputTokens,
    runTokenBudget: ctx.agent.limits.runTokenBudget,
    runTotalTokens: ctx.runTotalTokens,
    pressured: opts?.pressured,
    compaction: opts?.compaction,
  })

  ctx.emit(
    ctx.createRecord('metrics.context', {
      turn: ctx.turnIndex,
      breakdown,
    })
  )
}
