import type { AgentCtx } from './agent-ctx.js';
import type { AgentHook, HookDecision } from './hooks.js';
import { resolveDeliverable } from './deliverable.js';
export declare function deliverableRequiresNetworkPlane(deliverable: ReturnType<typeof resolveDeliverable>): boolean;
/** @deprecated use deliverableRequiresNetworkPlane — script 任务不强制 debugger。 */
export declare function taskNeedsNetworkPlane(deliverable: ReturnType<typeof resolveDeliverable>): boolean;
/** P0: try Network health; never hard-stop the run — degrade to DOM-only media path. */
export declare class NetworkPlaneHealthHook implements AgentHook {
    readonly name = "network-plane-health";
    readonly reads: readonly [{
        readonly key: "deliverable";
        readonly optional: true;
    }];
    runTaskPreflight(ctx: AgentCtx): Promise<string | undefined>;
    onStart(_ctx: AgentCtx): HookDecision;
}
/** P1: inject snapshot feed + block passive observe loops on media harvest. */
export declare class MediaHarvestMilestoneHook implements AgentHook {
    readonly name = "media-harvest-milestone";
    readonly reads: readonly [{
        readonly key: "deliverable";
        readonly optional: true;
    }, {
        readonly key: "mediaPassiveObserveEmpty";
        readonly optional: true;
    }];
    readonly writes: readonly ["mediaPassiveObserveEmpty"];
    runTaskPreflight(ctx: AgentCtx): Promise<string | undefined>;
    afterTool(ctx: AgentCtx): void;
    beforeTool(ctx: AgentCtx): HookDecision;
}
/** Block network tool calls after degrade — avoids list_failed HITL loops. */
export declare class NetworkDegradedToolGateHook implements AgentHook {
    readonly name = "network-degraded-tool-gate";
    beforeTool(ctx: AgentCtx): HookDecision;
}
