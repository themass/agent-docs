import type { DomPlane } from '@naviforge/dom-plane';
import type { AgentOptions, ExternalMcpTool, RunAgentResult } from './agent.js';
import type { SearchPlane } from './search-plane.js';
import type { FetchPlane } from './fetch-plane.js';
import type { NetworkPlane } from '@naviforge/network-plane';
import type { LlmConfig } from './llm.js';
export type ReadonlySubAgentOptions = {
    briefs: string[];
    parentRunId: string;
    parentSessionId?: string;
    anchorTabId?: number;
    dom: DomPlane;
    llm: LlmConfig;
    network?: NetworkPlane;
    mcpTools?: ExternalMcpTool[];
    callMcpTool?: AgentOptions['callMcpTool'];
    search?: SearchPlane;
    fetch?: FetchPlane;
    signal?: AbortSignal;
    maxSteps?: number;
    /** Audit sink for leaf runs — never forwarded to the parent ledger. */
    onLeafRecord?: AgentOptions['onLeafRecord'];
    onLeafSessionStart?: AgentOptions['onLeafSessionStart'];
    onLeafSessionComplete?: AgentOptions['onLeafSessionComplete'];
    createLeafPlanes?: AgentOptions['createLeafPlanes'];
    onTokenUsage?: AgentOptions['onTokenUsage'];
};
export type ReadonlyChildResult = {
    runId: string;
    parentRunId: string;
    status: RunAgentResult['status'];
    result?: string;
};
export type ReadonlyBatchResult = {
    children: ReadonlyChildResult[];
};
/**
 * Run up to three independent readonly leaves through the canonical Agent pipeline.
 * Each leaf owns its own trace sink and optional ephemeral tab scope; the parent
 * only receives the structured batch tool result.
 */
export declare function runReadonlySubAgents(opts: ReadonlySubAgentOptions): Promise<ReadonlyBatchResult>;
