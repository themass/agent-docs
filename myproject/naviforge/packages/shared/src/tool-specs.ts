import { AGENT_TOOL_CATALOG, type AgentToolId } from './agent-tools.js'

/** Risk class for model-facing tools (shown in tools[] description). */
export type ToolRisk = 'readonly' | 'mutating' | 'sensitive' | 'mixed'

export type ToolSpecMeta = {
  risk: ToolRisk
  /** Short when-to-use line; kept out of Kernel. */
  usage: string
}

/**
 * Single place for risk/usage metadata. Descriptions stay on AGENT_TOOL_CATALOG;
 * JSON Schema parameters stay in openai-tools META_SCHEMAS / TOOL_PARAMETERS.
 */
export const TOOL_SPEC_META: Record<AgentToolId, ToolSpecMeta> = {
  browser_observe: {
    risk: 'readonly',
    usage: '感知当前页；优先 PAGE STATE，再 snapshot/read/extract',
  },
  browser_act: {
    risk: 'mixed',
    usage: '写操作用 mutating action；scroll/highlight 等为 readonly-aux',
  },
  browser_nav: { risk: 'mutating', usage: '导航当前 tab；navigation:forbidden 时勿用' },
  tabs: { risk: 'mutating', usage: '开/切/关标签；渲染页用 open，静态 URL 优先 fetch_text' },
  web_search: { risk: 'readonly', usage: '未知来源或竞品对比时先搜；不是页内搜索框' },
  fetch_text: { risk: 'readonly', usage: '已知 HTTPS 静态 URL；媒体流用 network' },
  network: { risk: 'sensitive', usage: '须设置开启；media/hls 取流；禁止 dump cookie' },
  workspace: { risk: 'mutating', usage: '本机工作区读写与 script_save' },
  skill_load: { risk: 'readonly', usage: '按需加载 L2；已加载勿重复' },
  system_spawn_readonly_tasks: {
    risk: 'readonly',
    usage: '多 URL 并行只读或 navigation:forbidden 时委派子 Agent',
  },
  system_done: { risk: 'readonly', usage: '证据够立刻结束并给用户可见结论' },
  system_ask_user: { risk: 'readonly', usage: '提交/登录/支付等须确认时提问' },
  system_captcha_wait: { risk: 'readonly', usage: '等人机验证完成' },
}

export type ToolSpec = {
  id: AgentToolId
  group: (typeof AGENT_TOOL_CATALOG)[number]['group']
  description: string
  args: string
  risk: ToolRisk
  usage: string
}

export function getToolSpec(id: AgentToolId): ToolSpec {
  const row = AGENT_TOOL_CATALOG.find((tool) => tool.id === id)!
  const meta = TOOL_SPEC_META[id]
  return {
    id: row.id,
    group: row.group,
    description: row.description,
    args: row.args,
    risk: meta.risk,
    usage: meta.usage,
  }
}

export function formatToolApiDescription(id: AgentToolId): string {
  const spec = getToolSpec(id)
  return `${spec.description} [risk=${spec.risk}] ${spec.usage} (${spec.id})`
}

export const TOOL_SPECS: ToolSpec[] = AGENT_TOOL_IDS_SAFE()

function AGENT_TOOL_IDS_SAFE(): ToolSpec[] {
  return AGENT_TOOL_CATALOG.map((row) => getToolSpec(row.id))
}
