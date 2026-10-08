import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane';
import type { NetworkPlane } from '@naviforge/network-plane';
import type { RecordedDomAction } from '@naviforge/playbook';
import { type TraceRecord, type TraceRecordPayload, type TraceRecordType } from '@naviforge/session';
import { type TaskScope } from '@naviforge/policy';
import type { OpenAiFunctionTool, ToolCall, ToolResult } from '@naviforge/shared';
import type { AgentOptions, ExternalMcpTool, HitlController, MessageQueue, PauseController, RunAgentResult } from './agent.js';
import type { HookPipeline } from './hooks.js';
import { RunLedger } from './ledger.js';
import type { LlmConfig } from './llm.js';
import { type ThreadContext, type ThreadReuse } from './loop-gates.js';
import { type AgentGates } from './loop-gate-state.js';
import type { PageState } from './page-state.js';
import { type TaskContract } from './task-contract.js';
import { type RuntimeState } from './runtime-state.js';
import { type CapabilityStatus } from './capability-state.js';
import type { Evidence } from './evidence.js';
import type { RecoveryPlan } from './recovery.js';
import type { ModelDecision } from './failure.js';
import type { SearchPlane } from './search-plane.js';
import type { FetchPlane } from './fetch-plane.js';
import type { RecipePlane } from './recipe-plane.js';
import type { ScriptPlane } from './script-plane.js';
import type { TabsPlane } from './tabs-plane.js';
import { type ContextCompactor } from './working-set.js';
import type { WorkspacePlane } from './workspace-plane.js';
export type SkillSpec = NonNullable<AgentOptions['skills']>[number];
export type AgentPlanes = {
    /** dom_* / dom_read → dom-plane (extension content + chrome-dom-plane) */
    dom: DomPlane;
    /** network_read / network_intercept → network-plane */
    network?: NetworkPlane;
    /** tabs_* → tabs-plane */
    tabs?: TabsPlane;
    /** web_search → search-plane */
    search?: SearchPlane;
    /** fetch_text → fetch-plane */
    fetch?: FetchPlane;
    /** script_* → script-plane */
    scripts?: ScriptPlane;
    /** site recipe preflight / promotion */
    recipes?: RecipePlane;
    /** workspace / workspace_* → workspace-plane (host helper) */
    workspace?: WorkspacePlane;
};
/** I/O slice for `execTurn`. Not a third domain object — a bag of Agent/Ctx fields the tool runner may read. */
export type AgentIo = {
    runId: string;
    planes: AgentPlanes;
    snap: DomSnapshot;
    taskScope: TaskScope;
    llm: LlmConfig;
    signal?: AbortSignal;
    hitlPolicy: NonNullable<AgentOptions['hitlPolicy']>;
    rollbackUrlDrift: boolean;
    allowDomInject: boolean;
    allowNetworkIntercept: boolean;
    callMcpTool?: AgentOptions['callMcpTool'];
    mcpTools?: ExternalMcpTool[];
    skills?: AgentOptions['skills'];
    mainProbe?: AgentOptions['mainProbe'];
    visionShot?: {
        dataUrl?: string;
    };
    emit?: (record: TraceRecord) => void;
    chargeTokens?: (usage: {
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
    }) => void;
    createRecord: <Type extends TraceRecordType>(type: Type, payload: TraceRecordPayload[Type]) => TraceRecord;
    workspaceThread?: {
        threadId: string;
        slug?: string;
        title?: string;
        runId?: string;
    };
    locale?: string;
    parentSessionId?: AgentOptions['parentSessionId'];
    anchorTabId?: AgentOptions['anchorTabId'];
    createLeafPlanes?: AgentOptions['createLeafPlanes'];
    onLeafRecord?: AgentOptions['onLeafRecord'];
    onLeafSessionStart?: AgentOptions['onLeafSessionStart'];
    onLeafSessionComplete?: AgentOptions['onLeafSessionComplete'];
    gates: AgentGates;
};
export type AgentPolicy = {
    hitlPolicy: NonNullable<AgentOptions['hitlPolicy']>;
    allowDomInject: boolean;
    allowNetworkIntercept: boolean;
    allowedTools?: Set<string>;
    rollbackUrlDrift: boolean;
};
export type AgentLimits = {
    maxSteps: number;
    sameFailureLimit: number;
    sameActionLimit: number;
    runTimeoutMs: number;
    runTokenBudget: number;
    maxInputTokens: number;
};
export type AgentPrompt = {
    system: string;
    user: string;
    thread?: ThreadContext;
    loadedSkillText?: string;
};
/**
 * Capability bag assembled once from `AgentOptions` (Pi `Agent`, MAF `Agent`,
 * DSH seams). Mutating `skills` / `mcpTools` / `skillGuidance` here is how
 * `onStart` hooks change what the run can do. The loop lives in `agent.ts`.
 */
export declare class Agent {
    readonly opts: AgentOptions;
    readonly runId: ReturnType<typeof crypto.randomUUID>;
    readonly planes: AgentPlanes;
    readonly llm: LlmConfig;
    skills: SkillSpec[];
    mcpTools: ExternalMcpTool[];
    skillGuidance: string;
    threadContext?: ThreadContext;
    readonly policy: AgentPolicy;
    readonly profile?: NonNullable<AgentOptions['runProfile']>;
    readonly limits: AgentLimits;
    readonly contextCompactor: ContextCompactor;
    readonly hooks: HookPipeline;
    readonly hitl?: HitlController;
    readonly queue?: MessageQueue;
    readonly pause?: PauseController;
    readonly signal?: AbortSignal;
    readonly callMcpTool?: AgentOptions['callMcpTool'];
    readonly mainProbe?: AgentOptions['mainProbe'];
    readonly vision: boolean;
    /**
     * Bound by `agent.ts` (`Agent.prototype.run`) so this module does not import
     * the loop.
     */
    run(): Promise<RunAgentResult>;
    constructor(opts: AgentOptions);
}
/**
 * Per-run mutable working set passed to every hook (MAF `AgentContext`, Pi
 * `AgentContext` snapshot + loop locals). Assemble once after the first
 * snapshot; `beforeModel` refreshes `prompt` / `tools` / `messages`.
 */
export declare class AgentCtx {
    readonly agent: Agent;
    readonly ledger: RunLedger;
    readonly runId: string;
    task: string;
    taskId?: string;
    turnIndex: number | undefined;
    snap: DomSnapshot;
    taskScope: TaskScope;
    runTotalTokens: number;
    prompt: AgentPrompt;
    tools: OpenAiFunctionTool[];
    skills: SkillSpec[];
    skillGuidance: string;
    /** Projected working set (not the full ledger). Hooks may replace this. */
    messages: string[];
    imageDataUrl?: string;
    networkText: string;
    /** Deterministic page signal hydrate (inline scripts, DOM resources, network). */
    pageSignalsText: string;
    pageFrictionText: string;
    pageStateText: string;
    pageState?: PageState;
    completion?: {
        content: string;
        reasoning?: string;
        toolCalls?: Array<{
            name: string;
            arguments: Record<string, unknown>;
        }>;
    };
    decision?: ModelDecision;
    toolCall?: ToolCall;
    toolResult?: ToolResult;
    gates: AgentGates;
    recordedActions: RecordedDomAction[];
    recoveries: RecoveryPlan[];
    metadata: Record<string, unknown>;
    allowedTools?: Set<string>;
    visionShot: {
        dataUrl?: string;
    };
    /** Formatted execTurn trace for this step; set before `afterTool`. */
    toolTrace?: string;
    readonly reuse: ThreadReuse;
    /** Generic contract/state plane shared by all browser task types. */
    taskContract: TaskContract;
    runtimeState: RuntimeState;
    constructor(agent: Agent, snap: DomSnapshot);
    createRecord<Type extends TraceRecordType>(type: Type, payload: TraceRecordPayload[Type]): TraceRecord;
    emit(record: TraceRecord): void;
    recordNote(line: string): void;
    chargeTokens(usage: {
        promptTokens: number;
        completionTokens: number;
        totalTokens: number;
    }): void;
    appendCompaction(payload: Extract<TraceRecord, {
        type: 'context.compaction';
    }>['payload']): void;
    recover(plan: RecoveryPlan): void;
    /** Refresh the generic task contract after a continuation/follow-up retarget. */
    syncTaskContract(): void;
    /** Project the latest deterministic page state into the generic Runtime State. */
    syncRuntimePageState(): void;
    /** Add evidence without making domain-specific assumptions in the loop. */
    recordEvidence(input: Omit<Evidence, 'id' | 'at'> & {
        at?: number;
    }): void;
    /** Rebuild per-turn copies from the Agent bag. Extra hooks that must persist mutate `agent.*`. */
    syncFromAgent(): void;
    /** Rebuild `tools` from the Agent bag so a hook can add/remove MCP tools. */
    syncTools(): void;
    compileUser(): string;
    /**
     * Single source of truth for Network capability health. Every caller
     * (Hook preflight, media candidate retries, per-turn refresh) must route
     * through this so the capability-state transitions and the free-text
     * `networkText` can never disagree with each other.
     */
    refreshNetwork(): Promise<void>;
    /** Convenience read of the single Network capability truth. */
    networkCapabilityStatus(): CapabilityStatus;
    /**
     * True once Network capability has been marked `unavailable` (hard stop —
     * plane missing/removed, no automatic retry). Replaces the old
     * `metadata.networkDegraded` boolean so there is exactly one source of
     * truth. Any 'degrade and stop offering network tools' decision must read
     * this, never set a parallel flag.
     */
    get networkUnavailable(): boolean;
    /**
     * True while Network capability is `transient_error` and may still
     * recover (e.g. after a candidate click triggers a fresh attach).
     * Replaces `metadata.networkTransientError`.
     */
    get networkRetrySoon(): boolean;
    bindToolCall(decision: ModelDecision): void;
    applyToolArgs(): void;
    io(): AgentIo;
    retarget(task: string, taskId?: string): void;
}
