import { CONTEXT_BUDGET_RATIOS, inputTokenRatio, l1ProjectionCap, } from './context-budget.js';
import { estimatePromptTokens } from './context-compaction.js';
import { emitContextMetrics } from './emit-context-metrics.js';
import { buildToolCatalog } from './tool-catalog.js';
import { projectTraceRecords, promptWouldExceedInputLimit, estimateToolsTokens, } from './working-set.js';
import { interpretTurn, looksLikeSafetyRefusal, transportAskQuestion, } from './failure.js';
export const CONTINUE = { kind: 'continue' };
export class WorkingSetHook {
    name = 'working-set';
    reads = ['loadedSkillBodies'];
    onStart(ctx) {
        ctx.emit(ctx.createRecord('run.tools', { catalog: buildToolCatalog(ctx.tools) }));
        emitContextMetrics(ctx);
    }
    async beforeModel(ctx) {
        const maxInput = ctx.agent.limits.maxInputTokens;
        const take = (projectionCap) => {
            const projected = projectTraceRecords(ctx.ledger.all(), {
                maxInputTokens: projectionCap,
                ownerRunId: ctx.runId,
            });
            ctx.messages = [projected.prompt];
            ctx.prompt.loadedSkillText = ctx.gates.loadedSkillBodies.length
                ? ctx.gates.loadedSkillBodies.join('\n---\n')
                : undefined;
            ctx.prompt.user = ctx.compileUser();
            return projected.pressured;
        };
        const ratio = () => inputTokenRatio({
            system: ctx.prompt.system,
            user: ctx.prompt.user,
            tools: ctx.tools,
            maxInputTokens: maxInput,
        });
        const inputTokens = () => estimatePromptTokens({
            system: ctx.prompt.system,
            user: ctx.prompt.user,
            tools: ctx.tools,
        });
        const over = () => promptWouldExceedInputLimit({
            system: ctx.prompt.system,
            user: ctx.prompt.user,
            toolsTokens: estimateToolsTokens(ctx.tools),
            maxInputTokens: maxInput,
        });
        take(maxInput);
        let pressure = ratio() >= CONTEXT_BUDGET_RATIOS.soft;
        if (ratio() >= CONTEXT_BUDGET_RATIOS.soft) {
            pressure = take(l1ProjectionCap(maxInput, ratio())) || pressure;
        }
        emitContextMetrics(ctx, {
            pressured: pressure || ratio() >= CONTEXT_BUDGET_RATIOS.hard,
        });
        const priorPressure = Number(ctx.metadata.contextProjectionPressure ?? 0);
        ctx.metadata.contextProjectionPressure = pressure ? priorPressure + 1 : 0;
        const lastCompaction = [...ctx.ledger.all()]
            .reverse()
            .find((record) => record.type === 'context.compaction');
        const recordsSinceCompaction = lastCompaction
            ? ctx.ledger.all().filter((record) => record.at > lastCompaction.at).length
            : ctx.ledger.all().length;
        const shouldCompact = ratio() >= CONTEXT_BUDGET_RATIOS.hard ||
            over() ||
            Number(ctx.metadata.contextProjectionPressure) >= 2;
        const compactAllowed = !lastCompaction || recordsSinceCompaction >= 6;
        if (shouldCompact && compactAllowed) {
            try {
                const beforeTokens = inputTokens();
                const records = ctx.ledger.all();
                const compacted = await ctx.agent.contextCompactor.compact({
                    records,
                    constraints: projectTraceRecords(records, { maxInputTokens: 2_000, ownerRunId: ctx.runId }).items
                        .filter((entry) => entry.kind === 'constraint')
                        .map((entry) => entry.content),
                    openWork: projectTraceRecords(records, { maxInputTokens: 2_000, ownerRunId: ctx.runId }).items
                        .filter((entry) => entry.kind === 'error' || entry.kind === 'step')
                        .slice(-6)
                        .map((entry) => entry.content),
                });
                ctx.appendCompaction({
                    summary: compacted.summary,
                    coveredRecordIds: records.map((record) => record.id),
                    coveredRange: records.length ? { from: records[0].id, to: records.at(-1).id } : undefined,
                    preservedConstraints: compacted.preservedConstraints,
                    openWork: compacted.openWork,
                    tokenUsage: compacted.tokenUsage,
                    mode: compacted.mode ?? 'deterministic',
                });
                ctx.emit(ctx.createRecord('run.recovery', {
                    strategy: 'fold_context',
                    diagnostic: compacted.mode === 'llm'
                        ? `L2 LLM compaction covered ${records.length} audit records`
                        : `L2 deterministic compaction covered ${records.length} audit records`,
                }));
                take(l1ProjectionCap(maxInput, ratio()));
                const afterTokens = inputTokens();
                emitContextMetrics(ctx, {
                    pressured: ratio() >= CONTEXT_BUDGET_RATIOS.soft,
                    compaction: {
                        beforeTokens,
                        afterTokens,
                        coveredRecords: records.length,
                    },
                });
            }
            catch {
                take(Math.min(maxInput, 512));
            }
        }
        if (ratio() >= CONTEXT_BUDGET_RATIOS.stop || over()) {
            return { kind: 'stop', result: 'Model input limit exceeded after deterministic context projection.', status: 'error' };
        }
        return CONTINUE;
    }
}
export class ProtocolHook {
    maxRetries;
    name = 'protocol';
    // No ctx.gates reads/writes — decides purely from ctx.completion.
    invalidCount = 0;
    constructor(maxRetries = 1) {
        this.maxRetries = maxRetries;
    }
    afterModel(ctx) {
        if (!ctx.completion)
            throw new Error('ProtocolHook.afterModel: missing completion');
        const command = interpretTurn(ctx.completion);
        if (command.kind === 'proceed') {
            this.invalidCount = 0;
            return command;
        }
        if (command.kind !== 'retry_turn')
            return command;
        // A missing tool call that reads like a safety/policy refusal is not a
        // protocol slip the model can be coached out of — re-sending "you must
        // call exactly one tool" just reproduces the same refusal (the model is
        // declining the *task*, not confused about the *protocol*). Burning the
        // retry budget here only delays an identical outcome and surfaces as a
        // generic `run.error`, giving the user no indication the task itself was
        // declined. Stop immediately with `blocked` instead.
        if (looksLikeSafetyRefusal(ctx.completion.content ?? '') || looksLikeSafetyRefusal(ctx.completion.reasoning ?? '')) {
            const refusalText = (ctx.completion.content || ctx.completion.reasoning || '').trim();
            return {
                kind: 'stop',
                plan: {
                    strategy: 'protocol_error',
                    retryable: false,
                    diagnostic: `Model declined the task on safety/policy grounds: ${refusalText.slice(0, 300)}`,
                },
                result: refusalText || 'Task declined on safety/policy grounds.',
                status: 'blocked',
            };
        }
        this.invalidCount += 1;
        if (this.invalidCount > this.maxRetries) {
            return {
                kind: 'stop',
                plan: {
                    strategy: 'protocol_error',
                    retryable: false,
                    diagnostic: `${command.plan.diagnostic} (${this.invalidCount}/${this.maxRetries + 1} invalid completions)`,
                },
                result: command.plan.diagnostic,
            };
        }
        return {
            ...command,
            plan: {
                ...command.plan,
                diagnostic: `${command.plan.diagnostic} (retry ${this.invalidCount}/${this.maxRetries + 1})`,
            },
        };
    }
    reset() {
        this.invalidCount = 0;
    }
}
export class ToolOutcomeHook {
    policy;
    name = 'tool-outcome';
    reads = ['lastListHints'];
    constructor(policy) {
        this.policy = policy;
    }
    afterTool(ctx) {
        const result = ctx.toolResult;
        if (!result)
            return { notes: [] };
        if (result.ok) {
            this.policy.resetStreak();
            return { notes: [] };
        }
        return this.policy.onFailure({
            tool: ctx.toolCall?.tool ?? '',
            code: result.error.code,
            message: result.error.message,
            listHints: ctx.gates.lastListHints,
            locale: ctx.agent.opts.locale,
        });
    }
    resetStreak() {
        this.policy.resetStreak();
    }
}
export class ModelErrorHook {
    name = 'model-error';
    // No ctx.gates reads/writes — only reads ctx.metadata.modelError.
    onModelError(ctx) {
        const diagnostic = String(ctx.metadata.modelError ?? 'model request failed');
        return { kind: 'ask_user', question: transportAskQuestion(diagnostic, ctx.agent.opts.locale) };
    }
}
/**
 * `AgentGates` keys that `createAgentGates` initializes with a concrete
 * default (Set/Map/array/false/0 — see loop-gate-state.ts) rather than
 * leaving `undefined`. These are safe to read from turn one by construction
 * and are seeded into `validateHookOrdering`'s writer map up front, so only
 * the genuinely-optional (`?`) gate keys — the ones a specific hook must
 * populate before anyone downstream can rely on them — are checked for
 * ordering. Keep in sync with the non-optional fields of `AgentGates`.
 */
const GATES_WITH_RUN_START_DEFAULT = [
    'loadedSkillIds',
    'loadedSkillBodies',
    'jsCspBlocked',
    'seenObs',
    'lastObsByKey',
    'dupSkipByKey',
    'actionLoop',
    'lastListHints',
    'taskHintIssued',
    'stepsWithoutNewObs',
    'frictionHitlKeys',
    'runTabIds',
    'subtaskEvidenceReady',
    'tabsListProgressUsed',
    'pageVisits',
];
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
export function validateHookOrdering(hooks) {
    const warnings = [];
    const writtenBy = new Map(GATES_WITH_RUN_START_DEFAULT.map((key) => [key, 'createAgentGates (run-start default)']));
    for (const hook of hooks) {
        for (const entry of hook.reads ?? []) {
            const key = typeof entry === 'string' ? entry : entry.key;
            const optional = typeof entry === 'string' ? false : entry.optional;
            if (writtenBy.has(key))
                continue;
            const message = `hook ordering: '${hook.name}' reads gates.${key} but no earlier hook writes it (array order). ` +
                `Either move a writer before '${hook.name}', or confirm '${hook.name}' has a safe fallback and mark it { key: '${key}', optional: true } in reads.`;
            if (optional) {
                warnings.push(message);
            }
            else {
                throw new Error(message);
            }
        }
        for (const key of hook.writes ?? []) {
            if (!writtenBy.has(key))
                writtenBy.set(key, hook.name);
        }
    }
    return { warnings };
}
export class HookPipeline {
    hooks;
    constructor(hooks) {
        this.hooks = hooks;
        validateHookOrdering(hooks);
    }
    firstDecision(phase, ctx) {
        for (const hook of this.hooks) {
            const fn = hook[phase];
            if (!fn)
                continue;
            const out = fn.call(hook, ctx);
            if (out && out.kind !== 'continue')
                return out;
        }
        return CONTINUE;
    }
    onStart(ctx) {
        return this.firstDecision('onStart', ctx);
    }
    beforeStep(ctx) {
        return this.firstDecision('beforeStep', ctx);
    }
    async beforeModel(ctx) {
        ctx.syncFromAgent();
        for (const hook of this.hooks) {
            const out = await hook.beforeModel?.(ctx);
            if (out && out.kind !== 'continue')
                return out;
        }
        return CONTINUE;
    }
    onModelError(ctx) {
        return this.firstDecision('onModelError', ctx);
    }
    beforeTool(ctx) {
        return this.firstDecision('beforeTool', ctx);
    }
    afterModel(ctx) {
        let last = null;
        for (const hook of this.hooks) {
            if (!hook.afterModel)
                continue;
            const cmd = hook.afterModel(ctx);
            if (!cmd)
                continue;
            last = cmd;
            if (cmd.kind === 'proceed')
                ctx.decision = cmd.decision;
            if (cmd.kind !== 'proceed')
                return cmd;
        }
        if (!last)
            throw new Error('HookPipeline.afterModel: no protocol hook registered');
        return last;
    }
    afterTool(ctx) {
        let merged = { notes: [] };
        for (const hook of this.hooks) {
            if (!hook.afterTool)
                continue;
            const out = hook.afterTool(ctx);
            if (!out)
                continue;
            merged = {
                notes: [...merged.notes, ...out.notes],
                forceAsk: out.forceAsk ?? merged.forceAsk,
                markCsp: merged.markCsp || out.markCsp,
            };
        }
        return merged;
    }
    /** New task / HITL resume: protocol hint budget and same-failure streak. */
    resetTask() {
        for (const hook of this.hooks) {
            if (hook instanceof ProtocolHook)
                hook.reset();
            if (hook instanceof ToolOutcomeHook)
                hook.resetStreak();
        }
    }
    afterStep(ctx) {
        for (const hook of this.hooks)
            hook.afterStep?.(ctx);
    }
    onStop(ctx, result) {
        for (const hook of this.hooks)
            hook.onStop?.(ctx, result);
    }
    async runTaskPreflight(ctx) {
        for (const hook of this.hooks) {
            const result = await hook.runTaskPreflight?.(ctx);
            if (result)
                return result;
        }
        return undefined;
    }
}
