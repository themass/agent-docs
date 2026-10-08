import type { ToolResult } from '@naviforge/shared';
import type { RunAgentResult } from './agent.js';
import type { AgentCtx } from './agent-ctx.js';
import type { RecoveryPlan } from './recovery.js';
import { ToolOutcomePolicy, type ModelDecision, type LoopCommand, type ToolOutcome } from './failure.js';
export type { LoopCommand, ToolOutcome };
/**
 * Decision a hook returns. The loop executes; hooks mutate `AgentCtx` and/or
 * return a command. No `next()` onion — first non-`continue` wins at that phase.
 */
export type HookDecision = {
    kind: 'continue';
} | {
    kind: 'skip_tool';
    note: string;
    log?: string;
    result?: ToolResult;
    /** HITL question blocked by policy — loop emits `ask_user_blocked`. */
    blockedAsk?: {
        question: string;
        reason: string;
    };
    privacy?: {
        tool: string;
        code: string;
        hint: string;
    };
    stop?: boolean;
    stopResult?: string;
} | {
    kind: 'ask_user';
    question: string;
    plan?: RecoveryPlan;
} | {
    kind: 'stop';
    result: string;
    status?: RunAgentResult['status'];
} | {
    kind: 'retry_turn';
    hint: string;
    plan?: RecoveryPlan;
} | {
    kind: 'replace_decision';
    decision: ModelDecision;
};
export declare const CONTINUE: HookDecision;
/**
 * Named checkpoints around the loop (Pi AgentLoopConfig + MAF middleware layers +
 * Hermes pre/post LLM/tool, without Cordis/`next()`).
 *
 * Hooks may rewrite `ctx.prompt`, `ctx.tools`, `ctx.skills`, `ctx.messages`,
 * `ctx.toolCall.arguments`. They must not own Chrome / LLM I/O.
 */
/**
 * `AgentGates` keys a hook may read or write. Declaring these lets
 * `validateHookOrdering` catch "hook A reads a gate before hook B (which
 * writes it) has run" at pipeline-construction time instead of as a silent
 * mid-run state bug (see docs/BEST_PRACTICES_REVIEW.md section 4 P0 — this is
 * the same class of risk that caused the deliverable cross-turn drift fixed
 * in GENERAL_BROWSER_AGENT_REFACTOR_PHASE_1.md section 9).
 *
 * Keep this union in sync with `AgentGates` (loop-gate-state.ts). It is
 * intentionally a plain string union, not `keyof AgentGates`, to avoid an
 * import cycle between hooks.ts and loop-gate-state.ts.
 */
export type GateKey = 'loadedSkillIds' | 'loadedSkillBodies' | 'jsCspBlocked' | 'seenObs' | 'lastObsByKey' | 'dupSkipByKey' | 'actionLoop' | 'lastListHints' | 'taskHintIssued' | 'stepsWithoutNewObs' | 'frictionHitlKeys' | 'lastPageFriction' | 'runTabIds' | 'subtaskEvidenceReady' | 'tabsListProgressUsed' | 'pageVisits' | 'taskIntent' | 'deliverable' | 'scriptLoginAskIssued' | 'scriptSaved' | 'scriptSavePath' | 'recipeUsed' | 'recipeId' | 'mediaPassiveObserveEmpty' | 'inertActionIndexes' | 'lastPageStateFor';
export interface AgentHook {
    readonly name: string;
    onStart?(ctx: AgentCtx): HookDecision | void;
    onStop?(ctx: AgentCtx, result: RunAgentResult): void;
    beforeStep?(ctx: AgentCtx): HookDecision | void;
    afterStep?(ctx: AgentCtx): void;
    beforeModel?(ctx: AgentCtx): HookDecision | void | Promise<HookDecision | void>;
    afterModel?(ctx: AgentCtx): LoopCommand | void;
    onModelError?(ctx: AgentCtx): HookDecision | void;
    beforeTool?(ctx: AgentCtx): HookDecision | void;
    afterTool?(ctx: AgentCtx): ToolOutcome | void;
    /** Deterministic reads before the model loop; first non-empty result wins. */
    runTaskPreflight?(ctx: AgentCtx): Promise<string | undefined>;
    /**
     * `ctx.gates` keys this hook reads. Mark an entry
     * `{ key, optional: true }` when the hook has a safe fallback (e.g.
     * `ctx.gates.deliverable ?? resolveDeliverable(ctx.task)`) so an ordering
     * violation against it is a warning, not a hard failure. Omit entirely if
     * the hook touches no gate state.
     */
    readonly reads?: readonly (GateKey | {
        readonly key: GateKey;
        readonly optional: true;
    })[];
    /** `ctx.gates` keys this hook writes (initializes or mutates). */
    readonly writes?: readonly GateKey[];
}
export declare class WorkingSetHook implements AgentHook {
    readonly name = "working-set";
    readonly reads: readonly ["loadedSkillBodies"];
    onStart(ctx: AgentCtx): void;
    beforeModel(ctx: AgentCtx): Promise<HookDecision>;
}
export declare class ProtocolHook implements AgentHook {
    private readonly maxRetries;
    readonly name = "protocol";
    private invalidCount;
    constructor(maxRetries?: number);
    afterModel(ctx: AgentCtx): LoopCommand;
    reset(): void;
}
export declare class ToolOutcomeHook implements AgentHook {
    private readonly policy;
    readonly name = "tool-outcome";
    readonly reads: readonly ["lastListHints"];
    constructor(policy: ToolOutcomePolicy);
    afterTool(ctx: AgentCtx): ToolOutcome;
    resetStreak(): void;
}
export declare class ModelErrorHook implements AgentHook {
    readonly name = "model-error";
    onModelError(ctx: AgentCtx): HookDecision;
}
/**
 * Checks that every hook's declared `reads` of a genuinely-optional gate key
 * (one with no `createAgentGates` default — see `GATES_WITH_RUN_START_DEFAULT`)
 * is satisfied by an earlier `writes` in `hooks` order. This covers both the
 * first-wins phases and the sequential `runTaskPreflight` phase (which —
 * unlike the other phases — calls every hook's `runTaskPreflight` in array
 * order until one returns non-empty, not just the first one with a
 * decision; see `HookPipeline.runTaskPreflight` below).
 *
 * This cannot catch every possible mistake (a hook can still read gate
 * state that nothing declares, or declare `reads`/`writes` that don't match
 * what its code actually touches) but it turns "someone reordered the
 * array and silently broke a dependency" from a production drift bug into
 * a thrown error at `createRunHooks()` call time. See
 * docs/BEST_PRACTICES_REVIEW.md section 4 P0.
 *
 * Hooks whose `reads` entry is `{ key, optional: true }` only produce a
 * warning (pushed onto the returned `warnings` array) instead of a thrown
 * violation, because they have a documented fallback for the unset case
 * (e.g. `ctx.gates.deliverable ?? resolveDeliverable(ctx.task)`).
 */
export declare function validateHookOrdering(hooks: readonly AgentHook[]): {
    warnings: string[];
};
export declare class HookPipeline {
    readonly hooks: readonly AgentHook[];
    constructor(hooks: readonly AgentHook[]);
    private firstDecision;
    onStart(ctx: AgentCtx): HookDecision;
    beforeStep(ctx: AgentCtx): HookDecision;
    beforeModel(ctx: AgentCtx): Promise<HookDecision>;
    onModelError(ctx: AgentCtx): HookDecision;
    beforeTool(ctx: AgentCtx): HookDecision;
    afterModel(ctx: AgentCtx): LoopCommand;
    afterTool(ctx: AgentCtx): ToolOutcome;
    /** New task / HITL resume: protocol hint budget and same-failure streak. */
    resetTask(): void;
    afterStep(ctx: AgentCtx): void;
    onStop(ctx: AgentCtx, result: RunAgentResult): void;
    runTaskPreflight(ctx: AgentCtx): Promise<string | undefined>;
}
