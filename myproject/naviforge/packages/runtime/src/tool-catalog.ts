import type { TraceRecordPayload } from '@naviforge/session'
import type { OpenAiFunctionTool } from '@naviforge/shared'

export type ToolCatalogEntry = TraceRecordPayload['run.tools']['catalog'][number]

/** Snapshot of the tools[] block sent to the model — audit/UI only. */
export function buildToolCatalog(tools: readonly OpenAiFunctionTool[]): ToolCatalogEntry[] {
  return tools.map((tool) => ({
    name: tool.function.name,
    description: tool.function.description ?? '',
    source: tool.function.name.startsWith('mcp__') ? 'mcp' : 'builtin',
  }))
}
