import { type ContextCompactionMetric } from '@naviforge/context-metrics';
import type { AgentCtx } from './agent-ctx.js';
export declare function emitContextMetrics(ctx: AgentCtx, opts?: {
    pressured?: boolean;
    compaction?: ContextCompactionMetric;
}): void;
