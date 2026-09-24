import { AGENT_TOOL_CATALOG } from '@naviforge/shared'

/** Built-in agent tools shown in 插件管理 → Tools (derived from shared catalog). */
export const BUILTIN_TOOL_CATALOG = AGENT_TOOL_CATALOG.map(({ id, group, description }) => ({
  id,
  group,
  description,
}))
