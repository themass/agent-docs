import type { AgentCtx } from '../agent-ctx.js';
import type { PageFrictionReport } from './types.js';
export declare function shouldRefreshPageFriction(tool: string | undefined): boolean;
export type PageFrictionApplyResult = {
    report: PageFrictionReport | null;
    forceAsk?: string;
    notes: string[];
};
export declare function applyPageFrictionToCtx(ctx: AgentCtx, opts?: {
    tool?: string;
    bodyText?: string;
    skipJs?: boolean;
}): Promise<PageFrictionApplyResult>;
