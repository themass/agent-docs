import { MAX_EXPOSED_MCP_TOOLS, mcpQualifiedName, parseMcpQualifiedName } from '@naviforge/shared'
import type { ToolResult } from '@naviforge/shared'

export type McpToolListing = {
  serverId: string
  serverName: string
  name: string
  description?: string
  inputSchema: unknown
}

/** Maximum MCP tools exposed to one model call and eligible for Host execution. */
export const MCP_TOOL_CAP = MAX_EXPOSED_MCP_TOOLS

/**
 * Freeze the exact MCP catalog for a model call. This projection is also the
 * only catalog accepted when resolving a returned qualified tool name.
 */
export function exposeMcpTools(tools: readonly McpToolListing[] | undefined): readonly McpToolListing[] {
  return Object.freeze((tools ?? []).slice(0, MCP_TOOL_CAP).map((tool) => Object.freeze({ ...tool })))
}

/**
 * L1 catalog for the user prompt: each authorized MCP tool is a first-class
 * `mcp__server__tool` with its inputSchema.
 */
export function formatMcpToolCatalog(tools: readonly McpToolListing[] | undefined): string | undefined {
  const exposed = exposeMcpTools(tools)
  if (!exposed.length) return undefined
  return exposed
    .map((tool) => {
      const q = mcpQualifiedName(tool.serverId, tool.name)
      const desc = tool.description?.trim() || `${tool.serverName}.${tool.name}`
      const schema = JSON.stringify(tool.inputSchema ?? { type: 'object', properties: {} })
      return `- ${q} — ${desc}\n  serverId=${tool.serverId} tool=${tool.name}\n  arguments: ${schema}`
    })
    .join('\n')
    .slice(0, 12_000)
}

export type ResolvedMcpCall = {
  serverId: string
  tool: string
  arguments: Record<string, unknown>
}

/** Resolve `mcp__server__tool` (+ args = that tool's input fields). */
export function resolveMcpCall(
  toolName: string,
  args: Record<string, unknown>,
  listings: McpToolListing[] | readonly McpToolListing[] | undefined
): { ok: true; call: ResolvedMcpCall } | { ok: false; message: string } {
  const parsed = parseMcpQualifiedName(toolName)
  if (!parsed) {
    return { ok: false, message: `not an MCP tool: ${toolName}` }
  }

  const match = exposeMcpTools(listings ? [...listings] : undefined).find(
    (item) =>
      item.serverId === parsed.server &&
      item.name === parsed.tool &&
      mcpQualifiedName(item.serverId, item.name) === toolName
  )
  if (!match) {
    return {
      ok: false,
      message: `MCP tool "${toolName}" is not in this run's authorized catalog`,
    }
  }
  return {
    ok: true,
    call: { serverId: match.serverId, tool: match.name, arguments: args },
  }
}

export async function invokeResolvedMcpCall(
  call: ResolvedMcpCall,
  invoke: (
    serverId: string,
    tool: string,
    args: Record<string, unknown>
  ) => Promise<ToolResult>
): Promise<ToolResult> {
  return invoke(call.serverId, call.tool, call.arguments)
}
