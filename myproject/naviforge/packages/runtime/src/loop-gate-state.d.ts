import type { ListOpenHint } from './run-limits.js';
import type { PageVisit } from './page-cache.js';
import { type ActionLoopGate } from './loop-gates.js';
export type RunTabSummary = {
    id: number;
    url?: string;
    title?: string;
    active: boolean;
    windowId?: number;
};
/** Per-run gate state for observation dedupe, action loops, and skill stickiness. */
export type AgentGates = {
    loadedSkillIds: Set<string>;
    loadedSkillBodies: string[];
    jsCspBlocked: Set<string>;
    seenObs: Set<string>;
    lastObsByKey: Map<string, string>;
    dupSkipByKey: Map<string, number>;
    actionLoop: ActionLoopGate;
    lastListHints: ListOpenHint[];
    taskHintIssued: boolean;
    /** Consecutive tool steps without a new observation key (loop guard). */
    stepsWithoutNewObs: number;
    /** HITL already issued per url+friction kind (avoid repeat captcha prompts). */
    frictionHitlKeys: Set<string>;
    lastPageFriction?: {
        url: string;
        report: import('./page-friction/types.js').PageFrictionReport;
        at: number;
    };
    /** Tabs opened or switched to during this run (for scoped tabs_list). */
    runTabIds: Set<number>;
    /** Readonly subtasks returned usable evidence. */
    subtaskEvidenceReady: boolean;
    /** First tabs_list per run counts as progress; repeats do not. */
    tabsListProgressUsed: boolean;
    /** URL fingerprints visited this run (tabs_open / dom_read). */
    pageVisits: Map<string, PageVisit>;
    /** Resolved once per run for intent routing. */
    taskIntent?: import('./task-intent.js').TaskIntent;
    /** Primary deliverable narrative (Phase A). */
    deliverable?: import('./deliverable.js').Deliverable;
    scriptLoginAskIssued?: boolean;
    /** Successful script_save this run (Phase C verify). */
    scriptSaved?: boolean;
    scriptSavePath?: string;
    /** SiteRecipe preflight succeeded without LLM. */
    recipeUsed?: boolean;
    recipeId?: string;
    /** Passive browser_observe extract/read returning empty (media milestone). */
    mediaPassiveObserveEmpty?: number;
    /**
     * Generic click targets (keyed `${url}#${index}`) that produced no
     * observable effect (no URL/DOM/Page-State/Network change). Any
     * click-and-check flow should consult this before retrying an index.
     * See post-action-verify.ts.
     */
    inertActionIndexes?: Set<string>;
    /**
     * `(url, snapshot revision)` PAGE STATE was last computed for. Lets
     * attachPageState skip recompute + duplicate PAGE STATE note emission
     * when called again with nothing changed (e.g. once at run start, once
     * more from PreflightHook — both before any navigation/click happens).
     */
    lastPageStateFor?: {
        url: string;
        revision: number;
    };
};
export declare function createAgentGates(sameActionLimit: number): AgentGates;
export declare function resetTurnGates(gates: AgentGates): void;
export declare function markObservationSeen(gates: AgentGates, key: string, trace: string): void;
export declare function observationAlreadySeen(gates: AgentGates, key: string | null): boolean;
export declare function bumpDuplicateSkip(gates: AgentGates, key: string): number;
export declare function priorObservation(gates: AgentGates, key: string): string | undefined;
export declare function recordListHints(gates: AgentGates, hints: ListOpenHint[]): void;
export declare function recordLoadedSkill(gates: AgentGates, id: string, body?: string): void;
export declare function recordRunTab(gates: AgentGates, tabId: number): void;
/** Enough material to synthesize an answer without more tabs_list loops. */
export declare function hasSynthesisEvidence(gates: AgentGates): boolean;
export declare function scopeTabsToRun(tabs: RunTabSummary[], gates: AgentGates, anchorTabId?: number): {
    tabs: RunTabSummary[];
    scoped: boolean;
    totalBrowserTabs: number;
    hint: string;
};
