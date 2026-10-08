import type { AgentCtx } from './agent-ctx.js';
import { HookPipeline, ProtocolHook, ToolOutcomeHook, type AgentHook, type HookDecision } from './hooks.js';
/** Deterministic DOM reads before the model loop (list extract, top-N mark, page read). */
export declare class PreflightHook implements AgentHook {
    readonly name = "preflight";
    readonly writes: readonly ["deliverable", "taskIntent", "recipeUsed", "recipeId", "loadedSkillIds", "loadedSkillBodies"];
    runTaskPreflight(ctx: AgentCtx): Promise<string | undefined>;
}
export declare class SkillAllowlistHook implements AgentHook {
    readonly name = "skill-allowlist";
    beforeTool(ctx: AgentCtx): HookDecision;
}
/** Hard capability boundary for leaf runs; unlike skill allowlists, no system-tool bypass exists. */
export declare class RunProfileHook implements AgentHook {
    readonly name = "run-profile";
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class SensitiveToolHook implements AgentHook {
    readonly name = "sensitive-tool";
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class DuplicateSkillHook implements AgentHook {
    readonly name = "duplicate-skill";
    readonly reads: readonly ["loadedSkillIds"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class CspSkipHook implements AgentHook {
    readonly name = "csp-skip";
    readonly reads: readonly ["jsCspBlocked"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class PageCacheHook implements AgentHook {
    readonly name = "page-cache";
    readonly reads: readonly [{
        readonly key: "taskIntent";
        readonly optional: true;
    }, "pageVisits"];
    beforeTool(ctx: AgentCtx): HookDecision;
    afterTool(ctx: AgentCtx): void;
}
export declare class ScriptDeliverableStepHook implements AgentHook {
    readonly name = "script-deliverable-step";
    readonly reads: readonly [{
        readonly key: "deliverable";
        readonly optional: true;
    }, {
        readonly key: "scriptLoginAskIssued";
        readonly optional: true;
    }];
    readonly writes: readonly ["scriptLoginAskIssued"];
    beforeStep(ctx: AgentCtx): HookDecision;
}
export declare class ScriptLoginNavigateHook implements AgentHook {
    readonly name = "script-login-navigate";
    readonly reads: readonly [{
        readonly key: "deliverable";
        readonly optional: true;
    }];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class LoginLinkReadHook implements AgentHook {
    readonly name = "login-link-read";
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class DeliverableVerifyHook implements AgentHook {
    readonly name = "deliverable-verify";
    readonly reads: readonly [{
        readonly key: "deliverable";
        readonly optional: true;
    }, "scriptSaved", "subtaskEvidenceReady"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class DedupeObservationHook implements AgentHook {
    readonly name = "dedupe-observation";
    readonly reads: readonly ["seenObs", "dupSkipByKey", "lastObsByKey", {
        readonly key: "deliverable";
        readonly optional: true;
    }];
    readonly writes: readonly ["dupSkipByKey"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class ActionLoopHook implements AgentHook {
    readonly name = "action-loop";
    readonly reads: readonly ["actionLoop"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare class TaskHintHook implements AgentHook {
    readonly name = "task-hint";
    readonly reads: readonly ["taskHintIssued", {
        readonly key: "deliverable";
        readonly optional: true;
    }];
    readonly writes: readonly ["taskHintIssued", "taskIntent"];
    beforeStep(ctx: AgentCtx): HookDecision;
}
/** Success-path memory: sticky skill, list hints, observation/action-loop counters. */
export declare class ToolStateHook implements AgentHook {
    readonly name = "tool-state";
    readonly reads: readonly ["actionLoop", "tabsListProgressUsed", "seenObs"];
    readonly writes: readonly ["lastListHints", "loadedSkillIds", "loadedSkillBodies", "scriptSaved", "scriptSavePath", "runTabIds", "subtaskEvidenceReady", "seenObs", "lastObsByKey", "tabsListProgressUsed", "stepsWithoutNewObs", "actionLoop"];
    afterTool(ctx: AgentCtx): void;
}
export declare class NoProgressHook implements AgentHook {
    readonly name = "no-progress";
    readonly reads: readonly ["stepsWithoutNewObs"];
    beforeTool(ctx: AgentCtx): HookDecision;
}
export declare function createRunHooks(sameFailureLimit: number, extra?: readonly AgentHook[], protocolMaxRetries?: number): {
    pipeline: HookPipeline;
    protocol: ProtocolHook;
    tools: ToolOutcomeHook;
};
