import { createTraceRecord } from '@naviforge/session';
import { Agent, AgentCtx } from './agent-ctx.js';
import { transitionCapability } from './capability-state.js';
import { classifyFailure, isAbortError } from './recovery.js';
import { fillCopy, uiCopy } from './ui-copy.js';
import { resolveTaskScope } from '@naviforge/policy';
import { resetTurnGates } from './loop-gate-state.js';
import { runModelTurns } from './model-turns.js';
import { ensureAnchorTask, syncDeliverableFromTask } from './execution-task.js';
import { attachPageState } from './pi-run-loop.js';
import { READONLY_RUN_PROFILE } from './run-profile.js';
import { snapshotWithRetry } from './exec-turn.js';
export { formatActingDetail } from './acting-detail.js';
export { isToolAllowed, isCspEvalError, normalizeScrollArgs, formatReadPageTrace, formatExtractDomTrace, formatExtractContentTrace, formatToolTrace, } from './exec-turn.js';
export { formatWebSearchTrace } from './search-plane.js';
export { clampFetchMaxChars, formatFetchTextTrace, normalizeFetchTextUrl, } from './fetch-plane.js';
export { observationDedupeKey, actionLoopKey, createActionLoopGate, decideActionLoop, recordActionLoopSuccess, replayActionLoop, urlsMatchForReuse, bareSkillId, isPageReadTask, isResearchTask, resolveTaskMode, shouldHintListThenDetail, requestedList, requestedTopN, } from './loop-gates.js';
export { runModelTurns } from './model-turns.js';
export { PreflightHook } from './builtin-hooks.js';
export { Agent, AgentCtx } from './agent-ctx.js';
export { createAgentGates, resetTurnGates } from './loop-gate-state.js';
export { READONLY_RUN_PROFILE };
export function createPauseController() {
    let paused = false;
    let wake = null;
    return {
        isPaused: () => paused,
        pause: () => {
            paused = true;
        },
        resume: () => {
            paused = false;
            wake?.();
            wake = null;
        },
        waitIfPaused: async (signal) => {
            while (paused) {
                signal?.throwIfAborted();
                await new Promise((resolve, reject) => {
                    let settled = false;
                    const finish = (fn) => {
                        if (settled)
                            return;
                        settled = true;
                        signal?.removeEventListener('abort', onAbort);
                        fn();
                    };
                    const onAbort = () => finish(() => reject(new DOMException('Aborted', 'AbortError')));
                    if (signal?.aborted) {
                        onAbort();
                        return;
                    }
                    signal?.addEventListener('abort', onAbort, { once: true });
                    wake = () => finish(resolve);
                });
            }
        },
    };
}
/** Promise gate for ask_user ↔ UI reply (HITL). */
export function createHitlGate() {
    let pending = null;
    // ponytail: UI may reply after ask_user emit before waitForReply registers; buffer one.
    let buffered = null;
    const clear = () => {
        if (!pending)
            return;
        pending.signal?.removeEventListener('abort', pending.onAbort);
        pending = null;
    };
    return {
        isWaiting: () => pending !== null || buffered !== null,
        question: () => pending?.question ?? null,
        reply(text) {
            const value = text.trim();
            if (!value)
                return false;
            if (pending) {
                const { resolve } = pending;
                clear();
                buffered = null;
                resolve(value);
                return true;
            }
            buffered = value;
            return true;
        },
        cancelWaiting() {
            buffered = null;
            if (!pending)
                return;
            const { reject } = pending;
            clear();
            reject(new DOMException('HITL cancelled', 'AbortError'));
        },
        waitForReply(question, signal) {
            if (pending) {
                const { reject } = pending;
                clear();
                reject(new Error('HITL superseded'));
            }
            if (buffered) {
                const answer = buffered;
                buffered = null;
                return Promise.resolve(answer);
            }
            return new Promise((resolve, reject) => {
                const onAbort = () => {
                    clear();
                    reject(new DOMException('Aborted', 'AbortError'));
                };
                if (signal?.aborted) {
                    reject(new DOMException('Aborted', 'AbortError'));
                    return;
                }
                signal?.addEventListener('abort', onAbort, { once: true });
                pending = { question, resolve, reject, onAbort, signal };
            });
        },
    };
}
export function createQueuedTask(text, id) {
    const value = text.trim();
    if (!value)
        return null;
    return { id: id ?? crypto.randomUUID(), text: value };
}
/** Steering applies immediately; follow-ups run one task at a time. */
export function createMessageQueue() {
    const steering = [];
    const followUps = [];
    return {
        steer(text) {
            const value = text.trim();
            if (value)
                steering.push(value);
        },
        followUp(text, id) {
            const item = createQueuedTask(text, id);
            if (!item || followUps.some((task) => task.id === item.id))
                return null;
            followUps.push(item);
            return item;
        },
        listFollowUps() {
            return followUps.map((task) => ({ ...task }));
        },
        setFollowUps(tasks) {
            followUps.length = 0;
            const seenIds = new Set();
            for (const task of tasks) {
                const item = createQueuedTask(task.text, task.id);
                if (item && !seenIds.has(item.id)) {
                    seenIds.add(item.id);
                    followUps.push(item);
                }
            }
        },
        updateFollowUp(id, text) {
            const index = followUps.findIndex((task) => task.id === id);
            if (index < 0)
                return;
            const value = text.trim();
            if (!value)
                followUps.splice(index, 1);
            else
                followUps[index] = { ...followUps[index], text: value };
        },
        removeFollowUp(id) {
            const index = followUps.findIndex((task) => task.id === id);
            if (index >= 0)
                followUps.splice(index, 1);
        },
        moveFollowUp(from, to) {
            if (from < 0 || from >= followUps.length || to < 0 || to >= followUps.length)
                return;
            const [item] = followUps.splice(from, 1);
            followUps.splice(to, 0, item);
        },
        drainSteering() {
            return steering.splice(0);
        },
        drainNextFollowUp() {
            return followUps.shift() ?? null;
        },
        pending() {
            return { steering: steering.length, followUp: followUps.length };
        },
        clear() {
            steering.length = 0;
            followUps.length = 0;
        },
    };
}
export async function runAgent(opts) {
    const agent = new Agent(opts);
    return runPiAgentLoop(agent);
}
/** Outer Pi loop: one task, then follow-up. Inner turns live in `runModelTurns`. */
async function runPiAgentLoop(agent) {
    const opts = agent.opts;
    const planes = agent.planes;
    let runStartedAt = Date.now();
    let hitlPauseAt = null;
    const pauseWallClock = () => {
        if (hitlPauseAt == null)
            hitlPauseAt = Date.now();
    };
    const resumeWallClock = () => {
        if (hitlPauseAt != null) {
            runStartedAt += Date.now() - hitlPauseAt;
            hitlPauseAt = null;
        }
    };
    const wallClockElapsed = () => Date.now() - runStartedAt;
    const finish = (ctx, status, result) => ({
        status,
        result,
        recordedActions: ctx.recordedActions,
        finalUrl: ctx.snap.url,
        recoveries: ctx.recoveries,
    });
    const emitEarly = (type, payload) => {
        opts.onRecord?.(createTraceRecord({
            type,
            payload,
            runId: agent.runId,
            parentRunId: opts.parentRunId,
            taskId: opts.taskId,
        }));
    };
    if (planes.network && agent.profile?.manageNetwork !== false) {
        const digestProbe = await planes.network.digest(1);
        if (digestProbe.ok) {
            emitEarly('run.log', { message: 'network digest ok (skip duplicate attach)' });
        }
        else {
            const started = await planes.network.start();
            if (started.ok) {
                emitEarly('run.log', { message: 'network debugger attached' });
                emitEarly('run.network', { attached: true, message: 'debugger attached' });
            }
        }
    }
    const first = await snapshotWithRetry(planes.dom);
    if (!first.ok) {
        emitEarly('run.error', { message: first.error.message });
        return {
            status: 'error',
            result: first.error.message,
            recordedActions: [],
            recoveries: [classifyFailure(first.error)],
        };
    }
    const ctx = new AgentCtx(agent, first.data);
    if (opts.networkDegradedNote?.trim()) {
        ctx.agent.planes.network = undefined;
        ctx.runtimeState = {
            ...ctx.runtimeState,
            capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'unavailable', {
                reason: opts.networkDegradedNote.trim(),
                incrementAttempt: true,
            }),
        };
        ctx.networkText = 'NETWORK: (degraded — DOM-only for this run)';
        ctx.recordNote(opts.networkDegradedNote.trim());
        ctx.syncTools();
    }
    await attachPageState(ctx);
    const pipeline = agent.hooks;
    const noteUsage = (usage) => {
        if (!usage)
            return;
        ctx.runTotalTokens += usage.totalTokens;
        opts.onTokenUsage?.(usage);
        ctx.emit(ctx.createRecord('metrics.tokens', {
            prompt: usage.promptTokens,
            completion: usage.completionTokens,
            total: usage.totalTokens,
            runTotal: ctx.runTotalTokens,
        }));
    };
    const budgetExceeded = () => {
        const { runTimeoutMs, runTokenBudget } = agent.limits;
        if (runTimeoutMs > 0 && wallClockElapsed() >= runTimeoutMs) {
            return fillCopy(uiCopy(agent.opts.locale).timeout, {
                minutes: Math.round(runTimeoutMs / 60_000),
            });
        }
        if (runTokenBudget > 0 && ctx.runTotalTokens >= runTokenBudget) {
            return fillCopy(uiCopy(agent.opts.locale).tokenBudget, {
                budget: runTokenBudget,
                used: ctx.runTotalTokens,
            });
        }
        return null;
    };
    const awaitHitl = async (question, stopOnCancel) => {
        pauseWallClock();
        try {
            if (!agent.hitl) {
                ctx.emit(ctx.createRecord('run.ask', {
                    question,
                    wait: 'user',
                }));
                return 'park';
            }
            const waiting = agent.hitl.waitForReply(question, agent.signal);
            ctx.emit(ctx.createRecord('run.ask', {
                question,
                wait: 'user',
            }));
            const answer = await waiting;
            ctx.recordNote(`USER ANSWER: USER ANSWER to "${question}": ${answer}`);
            ctx.emit(ctx.createRecord('run.log', { message: `↩ hitl: ${answer}` }));
            if (stopOnCancel && /^(停止|stop|取消|cancel)\b/i.test(answer.trim()))
                return 'stop';
            return 'continue';
        }
        finally {
            resumeWallClock();
        }
    };
    const injectSteering = () => {
        const steers = agent.queue?.drainSteering() ?? [];
        if (!steers.length)
            return;
        for (const text of steers) {
            ctx.recordNote(`USER CORRECTION: USER CORRECTION (obey over prior plan; stay on current page unless correction says otherwise): ${text}`);
        }
        ctx.emit(ctx.createRecord('user.steer', { texts: steers, phase: 'pre_model' }));
    };
    const maybeFollowUpNext = (previous) => {
        const next = agent.queue?.drainNextFollowUp() ?? null;
        if (!next)
            return false;
        ctx.recordNote(`FOLLOW-UP: previous=${previous.slice(0, 200)}`);
        ctx.recordNote(`FOLLOW-UP: NEW TASK: ${next.text}`);
        ctx.retarget(next.text, next.id);
        ctx.emit(ctx.createRecord('user.task', { text: next.text }));
        return true;
    };
    const applySkip = (decision) => {
        const chunks = [];
        let current = '';
        for (const line of decision.note.split('\n')) {
            if (!line)
                continue;
            if (/^(GUIDANCE|EVIDENCE|CONSTRAINT|OBSERVATION|STEP):/.test(line)) {
                if (current)
                    chunks.push(current);
                current = line;
            }
            else {
                current = current ? `${current} ${line}` : line;
            }
        }
        if (current)
            chunks.push(current);
        for (const chunk of chunks)
            ctx.recordNote(chunk);
        if (decision.privacy) {
            ctx.emit(ctx.createRecord('run.error', {
                message: decision.privacy.hint,
                code: decision.privacy.code,
                tool: decision.privacy.tool,
            }));
            return;
        }
        if (decision.blockedAsk) {
            ctx.emit(ctx.createRecord('run.error', {
                message: `ask_user blocked: ${decision.blockedAsk.reason} — "${decision.blockedAsk.question}"`,
                code: 'ask_user_blocked',
            }));
            return;
        }
        const call = ctx.toolCall;
        if (!call)
            return;
        if (decision.log)
            ctx.emit(ctx.createRecord('run.log', { message: decision.log }));
        if (decision.result) {
            ctx.emit(ctx.createRecord('tool.result', {
                tool: call.tool,
                arguments: call.arguments,
                ok: decision.result.ok,
                ...(decision.result.ok
                    ? { data: decision.result.data }
                    : { error: decision.result.error }),
            }));
        }
    };
    const hitlOutcome = async (question, stopOnCancel) => {
        const hitl = await awaitHitl(question, stopOnCancel);
        if (hitl === 'stop')
            return finish(ctx, 'cancelled', question);
        if (hitl === 'park')
            return finish(ctx, 'ask_user', question);
        return 'continue';
    };
    let stopped = null;
    try {
        const started = pipeline.onStart(ctx);
        if (started.kind === 'stop') {
            stopped = finish(ctx, started.status ?? 'error', started.result);
            pipeline.onStop(ctx, stopped);
            return stopped;
        }
        while (true) {
            ensureAnchorTask(ctx);
            ctx.syncTaskContract();
            syncDeliverableFromTask(ctx);
            ctx.taskScope = resolveTaskScope(ctx.task);
            agent.hooks.resetTask();
            let deterministicResult;
            resetTurnGates(ctx.gates);
            stopped = null;
            deterministicResult = await pipeline.runTaskPreflight(ctx);
            if (!stopped) {
                if (deterministicResult) {
                    ctx.emit(ctx.createRecord('run.mode', {
                        mode: 'deterministic',
                        detail: '当前页列表提取可直接由 DOM 工具完成，未调用模型。',
                    }));
                    ctx.emit(ctx.createRecord('run.result', { text: deterministicResult }));
                    stopped = finish(ctx, 'done', deterministicResult);
                }
                else {
                    stopped = await runModelTurns({
                        agent,
                        ctx,
                        finish,
                        budgetExceeded,
                        noteUsage,
                        injectSteering,
                        hitlOutcome,
                        applySkip,
                    });
                }
            }
            if (stopped &&
                (stopped.status === 'done' || stopped.status === 'max_steps') &&
                maybeFollowUpNext(stopped.result ?? stopped.status)) {
                continue;
            }
            if (stopped) {
                pipeline.onStop(ctx, stopped);
                return stopped;
            }
        }
    }
    catch (e) {
        if (isAbortError(e)) {
            stopped = finish(ctx, 'cancelled');
            pipeline.onStop(ctx, stopped);
            return stopped;
        }
        throw e;
    }
    finally {
        if (planes.network && agent.profile?.manageNetwork !== false)
            await planes.network.stop().catch(() => { });
    }
}
Agent.prototype.run = function () {
    return runPiAgentLoop(this);
};
