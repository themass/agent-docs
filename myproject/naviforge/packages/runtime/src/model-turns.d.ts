import type { Agent, AgentCtx } from './agent-ctx.js';
import type { RunAgentResult } from './agent.js';
import type { HookDecision } from './hooks.js';
export type ModelTurnsDeps = {
    agent: Agent;
    ctx: AgentCtx;
    finish: (ctx: AgentCtx, status: RunAgentResult['status'], result?: string) => RunAgentResult;
    budgetExceeded: () => string | null;
    noteUsage: (usage?: {
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
    }) => void;
    injectSteering: () => void;
    hitlOutcome: (question: string, stopOnCancel: boolean) => Promise<RunAgentResult | 'continue'>;
    applySkip: (decision: Extract<HookDecision, {
        kind: 'skip_tool';
    }>) => void;
};
/** Inner Pi loop: prepareNextTurn → steering → one model tool (one task scope). */
export declare function runModelTurns(deps: ModelTurnsDeps): Promise<RunAgentResult | null>;
