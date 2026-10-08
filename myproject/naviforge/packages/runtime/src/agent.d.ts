import type { DomPlane } from '@naviforge/dom-plane';
import type { TabsPlane } from './tabs-plane.js';
import type { SearchPlane } from './search-plane.js';
import type { FetchPlane } from './fetch-plane.js';
import type { RecipePlane } from './recipe-plane.js';
import type { ScriptPlane } from './script-plane.js';
import type { WorkspacePlane } from './workspace-plane.js';
import type { NetworkPlane } from '@naviforge/network-plane';
import type { ToolResult } from '@naviforge/shared';
import type { AgentHook } from './hooks.js';
import type { LlmConfig } from './llm.js';
import { type RecoveryPlan } from './recovery.js';
import type { ContextCompactor } from './working-set.js';
import { type HitlPolicyMode } from '@naviforge/policy';
import { type ThreadContext } from './loop-gates.js';
import { READONLY_RUN_PROFILE, type RunProfile } from './run-profile.js';
import type { RecordedDomAction } from '@naviforge/playbook';
export { formatActingDetail } from './acting-detail.js';
export { isToolAllowed, isCspEvalError, normalizeScrollArgs, formatReadPageTrace, formatExtractDomTrace, formatExtractContentTrace, formatToolTrace, } from './exec-turn.js';
export { formatWebSearchTrace } from './search-plane.js';
export { clampFetchMaxChars, formatFetchTextTrace, normalizeFetchTextUrl, } from './fetch-plane.js';
export { observationDedupeKey, actionLoopKey, createActionLoopGate, decideActionLoop, recordActionLoopSuccess, replayActionLoop, urlsMatchForReuse, bareSkillId, isPageReadTask, isResearchTask, resolveTaskMode, shouldHintListThenDetail, requestedList, requestedTopN, type ActionLoopCall, type ActionLoopGate, type ThreadContext, type ThreadReuse, } from './loop-gates.js';
export { runModelTurns } from './model-turns.js';
export { PreflightHook } from './builtin-hooks.js';
export { Agent, AgentCtx } from './agent-ctx.js';
export { type AgentGates, createAgentGates, resetTurnGates } from './loop-gate-state.js';
export type { RecordedDomAction };
/**
 * Where an event sits in the loop. Stamped centrally by `runAgent`, so every
 * projection of the trace can group by task and turn without re-deriving order.
 * `turn` is absent for work that happens outside a model turn (setup, deterministic reads).
 */
export type TraceMeta = {
    runId?: string;
    taskId?: string;
    turn?: number;
    parentRunId?: string;
};
export type PauseController = {
    isPaused: () => boolean;
    waitIfPaused: (signal?: AbortSignal) => Promise<void>;
};
/** Blocks the agent until the UI answers an ask_user question. */
export type HitlController = {
    waitForReply: (question: string, signal?: AbortSignal) => Promise<string>;
};
export type AgentOptions = {
    task: string;
    /** Session goal for deliverable / routing when `task` is a continuation cue (继续, continue, …). */
    taskAnchor?: string;
    /** Assigned by the run owner before runtime starts; all records share it. */
    runId?: ReturnType<typeof crypto.randomUUID>;
    /** Parent run for a bounded readonly leaf. */
    parentRunId?: string;
    /** Parent thread session id (leaf audit only). */
    parentSessionId?: string;
    /** Parent-locked target tab; leaf ephemeral tabs must not switch this. */
    anchorTabId?: number;
    /** Per-child ephemeral planes (isolated tab binding for parallel leaves). */
    createLeafPlanes?: (input: {
        childRunId: string;
        anchorTabId: number;
    }) => Promise<{
        dom: DomPlane;
        tabs?: TabsPlane;
        dispose: () => Promise<void>;
    }> | {
        dom: DomPlane;
        tabs?: TabsPlane;
        dispose: () => Promise<void>;
    };
    /** Leaf trace sink — never merged into the parent ledger. */
    onLeafRecord?: (record: import('@naviforge/session').TraceRecord) => void;
    onLeafSessionStart?: (input: {
        childRunId: string;
        brief: string;
        index: number;
    }) => Promise<void | string>;
    onLeafSessionComplete?: (input: {
        childRunId: string;
        status: 'success' | 'failed' | 'cancelled';
    }) => void;
    /** Queue id of the first task, so per-task results stay attributable in the trace. */
    taskId?: string;
    dom: DomPlane;
    tabs?: TabsPlane;
    search?: SearchPlane;
    fetch?: FetchPlane;
    scripts?: ScriptPlane;
    recipes?: RecipePlane;
    llm: LlmConfig;
    network?: NetworkPlane;
    skillGuidance?: string;
    /**
     * Installed skills for progressive disclosure. Catalog (L1) goes in `skillGuidance`;
     * full bodies are returned only when the model calls `skill_load`.
     */
    skills?: Array<{
        id: string;
        version: string;
        description: string;
        instructions: string;
        tools?: string[];
        files?: string[];
    }>;
    /** Bounded, compressed context from prior runs in the active chat thread. */
    threadContext?: ThreadContext;
    /** Optional exact tool allowlist imposed by the selected skill. System terminal tools remain available. */
    allowedTools?: string[];
    /** Capability boundary for specialized runs. Normal runs omit this. */
    runProfile?: RunProfile;
    mcpTools?: ExternalMcpTool[];
    callMcpTool?: (serverId: string, tool: string, args: Record<string, unknown>) => Promise<ToolResult>;
    /** Allow dom_inject kind=script (settings gate). */
    allowDomInject?: boolean;
    /** Allow network_intercept / clearIntercepts (settings gate). */
    allowNetworkIntercept?: boolean;
    maxSteps?: number;
    /** Consecutive same tool+error.code failures before ask_user (default 2; 0 = off). */
    sameFailureLimit?: number;
    /** Max successful identical screenshot/scroll/snapshot per URL before blocking (default 2; 0 = off). */
    sameActionLimit?: number;
    /** Wall-clock limit for one Run in ms (default 8 min; 0 = off). */
    runTimeoutMs?: number;
    /** Stop when cumulative LLM tokens reach this (default 200_000; 0 = off). */
    runTokenBudget?: number;
    /** Maximum estimated tokens in one model input (system + user; 0 = off). */
    maxInputTokens?: number;
    /** @deprecated Use `runTokenBudget`. */
    tokenBudget?: number;
    /** Optional L2 semantic compactor; it never mutates the trace ledger. */
    contextCompactor?: ContextCompactor;
    signal?: AbortSignal;
    pause?: PauseController;
    /** Dual queues: steer corrects mid-run; followUp starts after stop. */
    queue?: MessageQueue;
    /** When set, ask_user waits for a reply instead of ending the run. */
    hitl?: HitlController;
    /** ask_user policy: strict blocks clarifications; balanced default; permissive allows most. */
    hitlPolicy?: HitlPolicyMode;
    /** Attempt history.back() after unexpected URL drift on stay-on-page tasks. */
    rollbackUrlDrift?: boolean;
    /** MAIN-world read-only probe (extension provides; requires allowMainProbe setting). */
    mainProbe?: (expression: string) => Promise<ToolResult<{
        value: unknown;
    }>>;
    /** Attach visible-tab screenshot to each LLM user message (multimodal models). */
    vision?: boolean;
    /** User-attached image for the initial task (composer / screenshot studio). */
    imageDataUrl?: string;
    imageLabel?: string;
    /** On-disk user workspace (Host). Screenshots and JSONL go here. */
    workspace?: WorkspacePlane;
    workspaceThread?: {
        threadId: string;
        slug?: string;
        title?: string;
        runId?: string;
    };
    /** UI locale for HITL / status copy and Reply language fallback (`en` | `zh-CN` | `es`). */
    locale?: string;
    /** Extension already tried CDP recovery; run continues without Network plane. */
    networkDegradedNote?: string;
    onRecord?: (record: import('@naviforge/session').TraceRecord) => void;
    /** Lets a child charge model usage to its owning run. */
    onTokenUsage?: (usage: {
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
    }) => void;
    saveCheckpoint?: (step: number, summary: string) => Promise<void>;
    /**
     * Extra hooks after the stock pipeline (working-set, protocol, tool gates).
     * May rewrite `ctx.prompt` / `ctx.tools` / `ctx.skills` / `ctx.messages`.
     */
    hooks?: AgentHook[];
};
export type ExternalMcpTool = {
    serverId: string;
    serverName: string;
    name: string;
    description?: string;
    inputSchema: unknown;
    /** Explicitly approved for a readonly child profile. */
    readonly?: boolean;
};
export { READONLY_RUN_PROFILE, type RunProfile };
export type RunAgentResult = {
    status: 'done' | 'ask_user' | 'blocked' | 'error' | 'cancelled' | 'max_steps';
    result?: string;
    /** Successful DOM click/type only — for Teach → Playbook. */
    recordedActions: RecordedDomAction[];
    finalUrl?: string;
    recoveries: RecoveryPlan[];
};
export declare function createPauseController(): PauseController & {
    pause: () => void;
    resume: () => void;
};
/** Promise gate for ask_user ↔ UI reply (HITL). */
export declare function createHitlGate(): HitlController & {
    reply: (text: string) => boolean;
    isWaiting: () => boolean;
    question: () => string | null;
    cancelWaiting: () => void;
};
export type QueuedTask = {
    id: string;
    text: string;
};
export declare function createQueuedTask(text: string, id?: string): QueuedTask | null;
export type MessageQueue = {
    steer: (text: string) => void;
    followUp: (text: string, id?: string) => QueuedTask | null;
    listFollowUps: () => QueuedTask[];
    setFollowUps: (tasks: QueuedTask[]) => void;
    updateFollowUp: (id: string, text: string) => void;
    removeFollowUp: (id: string) => void;
    moveFollowUp: (from: number, to: number) => void;
    drainSteering: () => string[];
    /** Take the next queued task for sequential execution. */
    drainNextFollowUp: () => QueuedTask | null;
    pending: () => {
        steering: number;
        followUp: number;
    };
    clear: () => void;
};
/** Steering applies immediately; follow-ups run one task at a time. */
export declare function createMessageQueue(): MessageQueue;
export declare function runAgent(opts: AgentOptions): Promise<RunAgentResult>;
