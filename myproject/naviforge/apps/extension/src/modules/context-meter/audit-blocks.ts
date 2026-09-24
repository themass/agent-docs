import type { ContextBlockMetric, ContextBreakdown } from '@naviforge/context-metrics'

/** Cursor-style rollup: fixed categories first, then page/trace details. */
const GROUPS: Array<{ id: string; members: string[]; always?: boolean }> = [
  { id: 'system', members: ['system'], always: true },
  { id: 'skill_catalog', members: ['skill_catalog'], always: true },
  { id: 'tools', members: ['tools'], always: true },
  { id: 'mcp_tools', members: ['mcp_tools'], always: true },
  { id: 'loaded_skills', members: ['skills'] },
  { id: 'user_prompt', members: ['task', 'reply_language', 'scope', 'instruction'] },
  { id: 'thread', members: ['thread'] },
  { id: 'page', members: ['browser', 'url', 'title', 'frames', 'snapshot'] },
  { id: 'network', members: ['network'] },
  { id: 'trace', members: ['trace'] },
]

const FALLBACK_LABELS: Record<string, string> = {
  system: 'System prompt',
  skill_catalog: 'Skill catalog',
  tools: 'API parameters (tools[])',
  mcp_tools: 'MCP API parameters',
  loaded_skills: 'Loaded skills',
  user_prompt: 'User prompt',
  thread: 'Thread / memory',
  page: 'Page context',
  network: 'Network',
  trace: 'Trace / summary',
}

export type ContextAuditLabels = Record<string, string>

function sumMembers(
  byId: Map<string, ContextBlockMetric>,
  members: string[]
): Pick<ContextBlockMetric, 'chars' | 'tokens'> {
  let chars = 0
  let tokens = 0
  for (const member of members) {
    const block = byId.get(member)
    if (!block) continue
    chars += block.chars
    tokens += block.tokens
  }
  return { chars, tokens }
}

/** Roll granular runtime blocks into audit rows; reconcile system budget when blocks omit kernel/tools. */
export function rollupContextAuditBlocks(
  breakdown: ContextBreakdown,
  labels: ContextAuditLabels
): ContextBlockMetric[] {
  const byId = new Map(breakdown.blocks.map((block) => [block.id, block]))
  const out: Array<ContextBlockMetric & { pinned?: boolean }> = []

  for (const group of GROUPS) {
    const { chars, tokens } = sumMembers(byId, group.members)
    if (tokens > 0 || group.always) {
      out.push({
        id: group.id,
        label: labels[group.id] ?? FALLBACK_LABELS[group.id] ?? group.id,
        chars,
        tokens,
        pinned: group.always,
      })
    }
  }

  const systemRow = out.find((row) => row.id === 'system')
  if (systemRow && systemRow.tokens === 0 && breakdown.systemTokens > 0) {
    systemRow.tokens = breakdown.systemTokens
  }

  const listed = out.reduce((sum, row) => sum + row.tokens, 0)
  const gap = breakdown.grandTotalTokens - listed
  if (gap > 32) {
    const toolsRow = out.find((row) => row.id === 'tools')
    if (toolsRow && toolsRow.tokens === 0) {
      toolsRow.tokens = gap
    } else if (systemRow) {
      systemRow.tokens += gap
    } else {
      out.unshift({
        id: 'system',
        label: labels.system ?? FALLBACK_LABELS.system!,
        chars: 0,
        tokens: gap,
      })
    }
  }

  return out.filter((row) => row.pinned || row.tokens > 0)
}
