import { MAX_EXPOSED_MCP_TOOLS, mcpQualifiedName, parseMcpQualifiedName } from '@naviforge/shared';
/** Maximum MCP tools exposed to one model call and eligible for Host execution. */
export const MCP_TOOL_CAP = MAX_EXPOSED_MCP_TOOLS;
/**
 * Freeze the exact MCP catalog for a model call. This projection is also the
 * only catalog accepted when resolving a returned qualified tool name.
 */
export function exposeMcpTools(tools) {
    return Object.freeze((tools ?? []).slice(0, MCP_TOOL_CAP).map((tool) => Object.freeze({ ...tool })));
}
/**
 * L1 catalog for the user prompt: each authorized MCP tool is a first-class
 * `mcp__server__tool` with its inputSchema.
 */
export function formatMcpToolCatalog(tools) {
    const exposed = exposeMcpTools(tools);
    if (!exposed.length)
        return undefined;
    return exposed
        .map((tool) => {
        const q = mcpQualifiedName(tool.serverId, tool.name);
        const desc = tool.description?.trim() || `${tool.serverName}.${tool.name}`;
        const schema = JSON.stringify(tool.inputSchema ?? { type: 'object', properties: {} });
        return `- ${q} — ${desc}\n  serverId=${tool.serverId} tool=${tool.name}\n  arguments: ${schema}`;
    })
        .join('\n')
        .slice(0, 12_000);
}
/** Resolve `mcp__server__tool` (+ args = that tool's input fields). */
export function resolveMcpCall(toolName, args, listings) {
    const parsed = parseMcpQualifiedName(toolName);
    if (!parsed) {
        return { ok: false, message: `not an MCP tool: ${toolName}` };
    }
    const match = exposeMcpTools(listings ? [...listings] : undefined).find((item) => item.serverId === parsed.server &&
        item.name === parsed.tool &&
        mcpQualifiedName(item.serverId, item.name) === toolName);
    if (!match) {
        return {
            ok: false,
            message: `MCP tool "${toolName}" is not in this run's authorized catalog`,
        };
    }
    return {
        ok: true,
        call: { serverId: match.serverId, tool: match.name, arguments: args },
    };
}
export async function invokeResolvedMcpCall(call, invoke) {
    return invoke(call.serverId, call.tool, call.arguments);
}
