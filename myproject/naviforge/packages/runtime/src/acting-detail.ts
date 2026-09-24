import { fillCopy, uiCopy } from './ui-copy.js'

/** Human-readable activity line for the side-panel status banner. */
export function formatActingDetail(
  tool: string | undefined,
  args?: Record<string, unknown>,
  locale?: string
): string {
  const copy = uiCopy(locale)
  if (!tool) return copy.acting
  if (tool === 'skill_load') {
    const id = typeof args?.id === 'string' ? args.id : ''
    return id ? fillCopy(copy.actingSkill, { id }) : copy.acting
  }
  if (tool.startsWith('mcp__')) return fillCopy(copy.actingMcp, { tool })
  if (tool === 'system_ask_user') return copy.actingAsk
  if (tool === 'system_done') return copy.actingDone
  if (tool === 'web_search') {
    const query = typeof args?.query === 'string' ? args.query.trim() : ''
    return query ? fillCopy(copy.actingSearch, { query: query.slice(0, 80) }) : copy.actingSearchEmpty
  }
  if (tool === 'fetch_text') {
    const url = typeof args?.url === 'string' ? args.url.trim() : ''
    return url
      ? fillCopy(copy.actingTool, { tool: `fetch_text ${url.slice(0, 72)}` })
      : fillCopy(copy.actingTool, { tool: 'fetch_text' })
  }
  if (tool === 'system_spawn_readonly_tasks') return copy.actingSub
  return fillCopy(copy.actingTool, { tool })
}
