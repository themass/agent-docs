import { formatDigest } from '@naviforge/network-plane';
import { createTraceRecord } from '@naviforge/session';
import { resolveTaskScope } from '@naviforge/policy';
import { AGENT_TOOL_IDS, buildChatTools } from '@naviforge/shared';
import { expandAgentToolCall } from './tools/builtin-tool-resolver.js';
import { createRunHooks } from './builtin-hooks.js';
import { RunLedger } from './ledger.js';
import { bareSkillId, observationDedupeKey, urlsMatchForReuse, } from './loop-gates.js';
import { createAgentGates, recordRunTab, resetTurnGates, } from './loop-gate-state.js';
import { buildTaskContract } from './task-contract.js';
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js';
import { createCapabilityRegistry, transitionCapability, capabilityUsable, capabilityRetryable, } from './capability-state.js';
import { lockDeliverable } from './deliverable.js';
import { composeSystemPrompt, compileUserPrompt } from './prompt.js';
import { resolveTaskMode } from './task-classifier.js';
import { DEFAULT_RUN_LIMITS } from './run-limits.js';
import { createContextCompactor } from './context-compaction.js';
import { WORKING_SET } from './working-set.js';
/**
 * Capability bag assembled once from `AgentOptions` (Pi `Agent`, MAF `Agent`,
 * DSH seams). Mutating `skills` / `mcpTools` / `skillGuidance` here is how
 * `onStart` hooks change what the run can do. The loop lives in `agent.ts`.
 */
export class Agent {
    opts;
    runId;
    planes;
    llm;
    skills;
    mcpTools;
    skillGuidance;
    threadContext;
    policy;
    profile;
    limits;
    contextCompactor;
    hooks;
    hitl;
    queue;
    pause;
    signal;
    callMcpTool;
    mainProbe;
    vision;
    /**
     * Bound by `agent.ts` (`Agent.prototype.run`) so this module does not import
     * the loop.
     */
    run() {
        throw new Error('Agent.run is attached by the runtime loop');
    }
    constructor(opts) {
        this.runId = opts.runId ?? crypto.randomUUID();
        this.opts = { ...opts, runId: this.runId };
        this.planes = {
            dom: opts.dom,
            network: opts.network,
            tabs: opts.tabs,
            search: opts.search,
            fetch: opts.fetch,
            scripts: opts.scripts,
            recipes: opts.recipes,
            workspace: opts.workspace,
        };
        this.llm = opts.llm;
        this.skills = [...(opts.skills ?? [])];
        this.mcpTools = [...(opts.mcpTools ?? [])];
        this.skillGuidance = opts.skillGuidance ?? '';
        this.threadContext = opts.threadContext;
        this.policy = {
            hitlPolicy: opts.hitlPolicy ?? 'balanced',
            allowDomInject: opts.allowDomInject === true,
            allowNetworkIntercept: opts.allowNetworkIntercept === true,
            allowedTools: opts.allowedTools?.length ? new Set(opts.allowedTools) : undefined,
            rollbackUrlDrift: opts.rollbackUrlDrift !== false,
        };
        this.profile = opts.runProfile;
        this.limits = {
            maxSteps: opts.maxSteps ?? DEFAULT_RUN_LIMITS.maxSteps,
            sameFailureLimit: opts.sameFailureLimit ?? DEFAULT_RUN_LIMITS.sameFailureLimit,
            sameActionLimit: opts.sameActionLimit ?? DEFAULT_RUN_LIMITS.sameActionLimit,
            runTimeoutMs: opts.runTimeoutMs ?? DEFAULT_RUN_LIMITS.runTimeoutMs,
            runTokenBudget: opts.runTokenBudget ?? opts.tokenBudget ?? DEFAULT_RUN_LIMITS.runTokenBudget,
            maxInputTokens: opts.maxInputTokens ?? DEFAULT_RUN_LIMITS.maxInputTokens,
        };
        this.contextCompactor =
            opts.contextCompactor ?? createContextCompactor({ llm: opts.llm, signal: opts.signal });
        this.hooks = createRunHooks(this.limits.sameFailureLimit, opts.hooks ?? [], opts.runProfile?.name === 'readonly-child' ? 4 : 1).pipeline;
        this.hitl = opts.hitl;
        this.queue = opts.queue;
        this.pause = opts.pause;
        this.signal = opts.signal;
        this.callMcpTool = opts.callMcpTool;
        this.mainProbe = opts.mainProbe;
        this.vision = opts.vision === true;
    }
}
/**
 * Per-run mutable working set passed to every hook (MAF `AgentContext`, Pi
 * `AgentContext` snapshot + loop locals). Assemble once after the first
 * snapshot; `beforeModel` refreshes `prompt` / `tools` / `messages`.
 */
export class AgentCtx {
    agent;
    ledger = new RunLedger();
    runId;
    task;
    taskId;
    turnIndex;
    snap;
    taskScope;
    runTotalTokens = 0;
    prompt;
    tools;
    skills;
    skillGuidance;
    /** Projected working set (not the full ledger). Hooks may replace this. */
    messages = [];
    imageDataUrl;
    networkText = 'NETWORK: (disabled)';
    /** Deterministic page signal hydrate (inline scripts, DOM resources, network). */
    pageSignalsText = '';
    pageFrictionText = '';
    pageStateText = '';
    pageState;
    completion;
    decision;
    toolCall;
    toolResult;
    gates;
    recordedActions = [];
    recoveries = [];
    metadata = {};
    allowedTools;
    visionShot = {};
    /** Formatted execTurn trace for this step; set before `afterTool`. */
    toolTrace;
    reuse;
    /** Generic contract/state plane shared by all browser task types. */
    taskContract;
    runtimeState;
    constructor(agent, snap) {
        this.agent = agent;
        this.runId = agent.runId;
        this.snap = snap;
        this.task = agent.opts.task;
        this.taskId = agent.opts.taskId;
        this.taskScope = resolveTaskScope(this.task);
        this.taskContract = buildTaskContract(this.task);
        this.runtimeState = createRuntimeState(this.taskContract, createCapabilityRegistry({
            dom: true,
            tabs: Boolean(agent.planes.tabs),
            network: Boolean(agent.planes.network),
            search: Boolean(agent.planes.search),
            fetch: Boolean(agent.planes.fetch),
            workspace: Boolean(agent.planes.workspace),
            hitl: Boolean(agent.hitl),
        }));
        this.skillGuidance = agent.skillGuidance;
        this.skills = [...agent.skills];
        this.allowedTools = agent.policy.allowedTools ? new Set(agent.policy.allowedTools) : undefined;
        this.prompt = {
            system: composeSystemPrompt(agent.skillGuidance, {
                hasMcpTools: agent.mcpTools.length > 0,
            }),
            user: '',
            thread: agent.threadContext,
        };
        const profileMcpTools = agent.profile?.allowReadonlyMcp
            ? agent.mcpTools.filter((tool) => tool.readonly)
            : agent.mcpTools;
        this.tools = buildChatTools(profileMcpTools, agent.profile ? { only: agent.profile.allowedTools } : undefined);
        this.reuse = agent.threadContext?.reuse ?? { skillIds: [] };
        this.gates = createAgentGates(agent.limits.sameActionLimit);
        for (const id of this.reuse.skillIds)
            this.gates.loadedSkillIds.add(bareSkillId(id));
        if (typeof agent.opts.anchorTabId === 'number') {
            recordRunTab(this.gates, agent.opts.anchorTabId);
        }
        const taskPayload = { text: this.task };
        if (agent.opts.imageDataUrl) {
            taskPayload.imageDataUrl = agent.opts.imageDataUrl;
            if (agent.opts.imageLabel)
                taskPayload.imageLabel = agent.opts.imageLabel;
            this.visionShot.dataUrl = agent.opts.imageDataUrl;
        }
        const taskRecord = this.createRecord('user.task', taskPayload);
        this.ledger.append(taskRecord);
        this.agent.opts.onRecord?.(taskRecord);
        if (this.reuse.page && urlsMatchForReuse(this.reuse.page.url, snap.url)) {
            const readKey = observationDedupeKey('dom_read', snap.url, { mode: 'body' });
            if (readKey) {
                this.gates.seenObs.add(readKey);
                this.gates.lastObsByKey.set(readKey, this.reuse.page.evidence);
                this.recordNote(`PREFLIGHT: reuse ${this.reuse.page.evidence.slice(0, WORKING_SET.evidenceChars)}`);
            }
        }
    }
    createRecord(type, payload) {
        return createTraceRecord({
            type,
            payload,
            runId: this.runId,
            parentRunId: this.agent.opts.parentRunId,
            taskId: this.taskId,
            turn: this.turnIndex,
        });
    }
    emit(record) {
        this.ledger.append(record);
        this.agent.opts.onRecord?.(record);
    }
    recordNote(line) {
        this.emit(this.createRecord('run.note', { text: line, topic: 'internal' }));
    }
    chargeTokens(usage) {
        this.runTotalTokens += usage.totalTokens;
        this.emit(this.createRecord('metrics.tokens', {
            prompt: usage.promptTokens,
            completion: usage.completionTokens,
            total: usage.totalTokens,
            runTotal: this.runTotalTokens,
        }));
    }
    appendCompaction(payload) {
        this.emit(this.createRecord('context.compaction', payload));
    }
    recover(plan) {
        this.recoveries.push(plan);
        this.emit(this.createRecord('run.recovery', { strategy: plan.strategy, diagnostic: plan.diagnostic }));
    }
    /** Refresh the generic task contract after a continuation/follow-up retarget. */
    syncTaskContract() {
        this.taskContract = buildTaskContract(this.task);
        this.runtimeState = { ...this.runtimeState, task: this.taskContract };
    }
    /** Project the latest deterministic page state into the generic Runtime State. */
    syncRuntimePageState() {
        if (!this.pageState)
            return;
        this.runtimeState = reduceRuntimeState(this.runtimeState, {
            type: 'page_state',
            page: this.pageState,
            snapshot: { revision: this.snap.revision, url: this.snap.url, title: this.snap.title },
        });
    }
    /** Add evidence without making domain-specific assumptions in the loop. */
    recordEvidence(input) {
        this.runtimeState = reduceRuntimeState(this.runtimeState, { type: 'evidence', evidence: input });
    }
    /** Rebuild per-turn copies from the Agent bag. Extra hooks that must persist mutate `agent.*`. */
    syncFromAgent() {
        this.skills = [...this.agent.skills];
        this.skillGuidance = this.agent.skillGuidance;
        this.allowedTools = this.agent.policy.allowedTools ? new Set(this.agent.policy.allowedTools) : undefined;
        this.prompt.system = composeSystemPrompt(this.agent.skillGuidance, {
            hasMcpTools: this.agent.mcpTools.length > 0,
        });
        this.prompt.thread = this.agent.threadContext;
        this.syncTools();
    }
    /** Rebuild `tools` from the Agent bag so a hook can add/remove MCP tools. */
    syncTools() {
        const profile = this.agent.profile;
        const mcpTools = profile?.allowReadonlyMcp
            ? this.agent.mcpTools.filter((tool) => tool.readonly)
            : this.agent.mcpTools;
        let only = profile ? profile.allowedTools : undefined;
        if (this.networkUnavailable) {
            const base = only ? [...only] : [...AGENT_TOOL_IDS];
            only = base.filter((id) => id !== 'network');
        }
        this.tools = buildChatTools(mcpTools, only ? { only } : undefined);
    }
    compileUser() {
        const deliverable = this.gates.deliverable ??
            lockDeliverable(typeof this.metadata.anchorTask === 'string' && this.metadata.anchorTask.trim()
                ? this.metadata.anchorTask.trim()
                : this.task.trim(), this.task);
        return compileUserPrompt(this.task, this.snap, this.messages, this.networkText, this.prompt.loadedSkillText ??
            (this.gates.loadedSkillBodies.length ? this.gates.loadedSkillBodies.join('\n---\n') : undefined), this.prompt.thread, this.agent.opts.locale, resolveTaskMode(this.task), this.pageSignalsText, this.pageFrictionText, this.pageStateText, this.pageState, deliverable);
    }
    /**
     * Single source of truth for Network capability health. Every caller
     * (Hook preflight, media candidate retries, per-turn refresh) must route
     * through this so the capability-state transitions and the free-text
     * `networkText` can never disagree with each other.
     */
    async refreshNetwork() {
        const network = this.agent.planes.network;
        if (!network) {
            this.networkText = 'NETWORK: (disabled)';
            return;
        }
        let digest = await network.digest(10);
        if (!digest.ok) {
            const started = await network.start();
            if (!started.ok) {
                this.runtimeState = {
                    ...this.runtimeState,
                    capabilities: transitionCapability(this.runtimeState.capabilities, 'network', 'transient_error', {
                        reason: started.error.message,
                        retryAt: Date.now() + 750,
                        incrementAttempt: true,
                    }),
                };
                this.networkText = `NETWORK: error ${started.error.message}`;
                return;
            }
            digest = await network.digest(10);
        }
        if (digest.ok) {
            this.runtimeState = {
                ...this.runtimeState,
                capabilities: transitionCapability(this.runtimeState.capabilities, 'network', 'available'),
            };
            this.networkText = formatDigest(digest.data);
        }
        else {
            this.runtimeState = {
                ...this.runtimeState,
                capabilities: transitionCapability(this.runtimeState.capabilities, 'network', 'transient_error', {
                    reason: digest.error.message,
                    retryAt: Date.now() + 750,
                    incrementAttempt: true,
                }),
            };
            this.networkText = `NETWORK: error ${digest.error.message}`;
        }
    }
    /** Convenience read of the single Network capability truth. */
    networkCapabilityStatus() {
        return this.runtimeState.capabilities.network.status;
    }
    /**
     * True once Network capability has been marked `unavailable` (hard stop —
     * plane missing/removed, no automatic retry). Replaces the old
     * `metadata.networkDegraded` boolean so there is exactly one source of
     * truth. Any 'degrade and stop offering network tools' decision must read
     * this, never set a parallel flag.
     */
    get networkUnavailable() {
        return !capabilityUsable(this.runtimeState.capabilities.network) &&
            this.runtimeState.capabilities.network.status === 'unavailable';
    }
    /**
     * True while Network capability is `transient_error` and may still
     * recover (e.g. after a candidate click triggers a fresh attach).
     * Replaces `metadata.networkTransientError`.
     */
    get networkRetrySoon() {
        return capabilityRetryable(this.runtimeState.capabilities.network);
    }
    bindToolCall(decision) {
        const expanded = expandAgentToolCall(decision.call.tool, { ...decision.call.arguments });
        this.toolCall = { tool: expanded.tool, arguments: expanded.arguments };
        this.toolResult = undefined;
    }
    applyToolArgs() {
        if (!this.decision || !this.toolCall)
            return;
        this.decision.call.arguments = this.toolCall.arguments;
        this.decision.call.tool = this.toolCall.tool;
    }
    io() {
        return {
            runId: this.runId,
            planes: this.agent.planes,
            snap: this.snap,
            taskScope: this.taskScope,
            llm: this.agent.llm,
            signal: this.agent.signal,
            hitlPolicy: this.agent.policy.hitlPolicy,
            rollbackUrlDrift: this.agent.policy.rollbackUrlDrift,
            allowDomInject: this.agent.policy.allowDomInject,
            allowNetworkIntercept: this.agent.policy.allowNetworkIntercept,
            callMcpTool: this.agent.callMcpTool,
            mcpTools: this.agent.mcpTools,
            skills: this.skills,
            mainProbe: this.agent.mainProbe,
            visionShot: this.visionShot,
            emit: (record) => this.emit(record),
            chargeTokens: (usage) => this.chargeTokens(usage),
            createRecord: (type, payload) => this.createRecord(type, payload),
            workspaceThread: this.agent.opts.workspaceThread,
            locale: this.agent.opts.locale,
            parentSessionId: this.agent.opts.parentSessionId,
            anchorTabId: this.agent.opts.anchorTabId,
            createLeafPlanes: this.agent.opts.createLeafPlanes,
            onLeafRecord: this.agent.opts.onLeafRecord,
            onLeafSessionStart: this.agent.opts.onLeafSessionStart,
            onLeafSessionComplete: this.agent.opts.onLeafSessionComplete,
            gates: this.gates,
        };
    }
    retarget(task, taskId) {
        this.task = task;
        this.taskId = taskId;
        this.turnIndex = undefined;
        this.syncTaskContract();
        this.taskScope = resolveTaskScope(task);
        resetTurnGates(this.gates);
    }
}
