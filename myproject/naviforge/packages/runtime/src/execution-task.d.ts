import type { AgentCtx } from './agent-ctx.js';
export declare function anchorTask(ctx: AgentCtx): string;
export declare function ensureAnchorTask(ctx: AgentCtx): string;
export declare function syncDeliverableFromTask(ctx: AgentCtx): void;
export declare function taskTextForRouting(ctx: AgentCtx): string;
/** Used by extension to decide network plane before run. */
export declare function taskRequiresNetworkPlane(task: string): boolean;
/** OR across follow-up text + session anchor (e.g. user sends「继续」). */
export declare function shouldEnableNetworkPlane(...tasks: string[]): boolean;
