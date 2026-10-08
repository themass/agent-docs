import type { DomPlane, DomSnapshot, SnapshotMode } from '@naviforge/dom-plane';
import type { NetworkPlane } from '@naviforge/network-plane';
import type { ToolResult } from '@naviforge/shared';
import type { BuiltinContext } from './types.js';
export declare function normalizeScrollArgs(args: Record<string, unknown>): {
    to?: 'top' | 'bottom' | 'y';
    y?: number;
    direction?: 'up' | 'down';
    amount?: number;
};
export declare function parseSnapshotMode(value: unknown): SnapshotMode | undefined;
export declare function withStaleRevisionRetry<T>(dom: DomPlane, snap: DomSnapshot, run: (revision: number) => Promise<ToolResult<T>>): Promise<{
    result: ToolResult<T>;
    snap: DomSnapshot;
}>;
export declare function networkAfter(network: NetworkPlane | undefined, after: number): Promise<import("@naviforge/network-plane").NetworkEvent | undefined>;
export declare function handlerPrelude(input: BuiltinContext): {
    turn: import("../../failure.js").ModelDecision;
    action: import("@naviforge/shared").ToolCall;
    ctx: import("../../agent-ctx.js").AgentIo;
    blockAsk: (question: string) => import("./types.js").ExecOut | null;
    dom: DomPlane;
    network: NetworkPlane | undefined;
    tabs: import("../../tabs-plane.js").TabsPlane | undefined;
    scripts: import("../../script-plane.js").ScriptPlane | undefined;
    taskScope: import("@naviforge/policy").TaskScope;
    callMcpTool: ((serverId: string, tool: string, args: Record<string, unknown>) => Promise<ToolResult>) | undefined;
    mcpTools: import("../../agent.js").ExternalMcpTool[] | undefined;
    allowDomInject: boolean;
    allowNetworkIntercept: boolean;
    skills: {
        id: string;
        version: string;
        description: string;
        instructions: string;
        tools?: string[];
        files?: string[];
    }[] | undefined;
    search: import("../../search-plane.js").SearchPlane | undefined;
    fetch: import("../../fetch-plane.js").FetchPlane | undefined;
    workspace: import("../../workspace-plane.js").WorkspacePlane | undefined;
};
