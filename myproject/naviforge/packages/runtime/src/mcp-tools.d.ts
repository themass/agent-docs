import type { ToolResult } from '@naviforge/shared';
export type McpToolListing = {
    serverId: string;
    serverName: string;
    name: string;
    description?: string;
    inputSchema: unknown;
};
/** Maximum MCP tools exposed to one model call and eligible for Host execution. */
export declare const MCP_TOOL_CAP = 30;
/**
 * Freeze the exact MCP catalog for a model call. This projection is also the
 * only catalog accepted when resolving a returned qualified tool name.
 */
export declare function exposeMcpTools(tools: readonly McpToolListing[] | undefined): readonly McpToolListing[];
/**
 * L1 catalog for the user prompt: each authorized MCP tool is a first-class
 * `mcp__server__tool` with its inputSchema.
 */
export declare function formatMcpToolCatalog(tools: readonly McpToolListing[] | undefined): string | undefined;
export type ResolvedMcpCall = {
    serverId: string;
    tool: string;
    arguments: Record<string, unknown>;
};
/** Resolve `mcp__server__tool` (+ args = that tool's input fields). */
export declare function resolveMcpCall(toolName: string, args: Record<string, unknown>, listings: McpToolListing[] | readonly McpToolListing[] | undefined): {
    ok: true;
    call: ResolvedMcpCall;
} | {
    ok: false;
    message: string;
};
export declare function invokeResolvedMcpCall(call: ResolvedMcpCall, invoke: (serverId: string, tool: string, args: Record<string, unknown>) => Promise<ToolResult>): Promise<ToolResult>;
