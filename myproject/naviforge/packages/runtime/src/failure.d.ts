import type { ToolCall } from '@naviforge/shared';
import { type ListOpenHint } from './run-limits.js';
import type { RecoveryPlan } from './recovery.js';
import type { RunAgentResult } from './agent.js';
/** Model-facing; CspSkipHook uses the same string. */
export declare const CSP_EXECUTE_JS_HINT = "GUIDANCE: execute_js blocked by page CSP on this URL; use snapshot/read_page or existing evidence \u2014 do not retry";
export type ChatCompletionLike = {
    content: string;
    reasoning?: string;
    toolCalls?: Array<{
        name: string;
        arguments: Record<string, unknown>;
    }>;
};
/** Command the loop executes. ProtocolHook owns retry budget; this only parses. */
export type LoopCommand = {
    kind: 'proceed';
    decision: ModelDecision;
} | {
    kind: 'retry_turn';
    plan: RecoveryPlan;
    hint: string;
} | {
    kind: 'stop';
    plan: RecoveryPlan;
    result: string;
    status?: RunAgentResult['status'];
};
/** Minimal internal representation of one native model decision. */
export type ModelDecision = {
    call: ToolCall;
    summary: string;
};
export declare const FETCH_TEXT_BATCH_MAX = 10;
/** Collect HTTPS URLs from one or more fetch_text tool calls (network-free). */
export declare function collectFetchTextUrls(calls: ReadonlyArray<{
    name: string;
    arguments: Record<string, unknown>;
}>): string[];
/** Merge parallel fetch_text calls into one batch tool call. */
export declare function coalesceFetchTextBatch(calls: ReadonlyArray<{
    name: string;
    arguments: Record<string, unknown>;
}>, summary: string): ModelDecision | null;
/**
 * Detect a model turn that is a content-safety / policy refusal rather than a
 * protocol slip (model forgot to call a tool, malformed arguments, etc).
 * Generic lexical patterns across zh/en — this is not a site/domain rule, it
 * is about the *shape* of a refusal (model declines to assist, cites policy,
 * safety, legality, or harm to a protected group) regardless of what page or
 * task triggered it.
 *
 * Why this matters: ProtocolHook's job is to push the model to retry when it
 * forgets the "exactly one tool call" protocol. Retrying a safety refusal
 * with the same GUIDANCE text just produces the same refusal again (model
 * will not call `system_done`/`system_ask_user` either, since from the
 * model's perspective calling *any* tool for this request is the thing it is
 * refusing to do). The loop must stop and surface `blocked`, not spin to
 * `run.error` after burning the retry budget on an unwinnable retry.
 */
export declare function looksLikeSafetyRefusal(text: string): boolean;
/** Require exactly one native function tool call; text is never executable. */
export declare function interpretTurn(completion: ChatCompletionLike): LoopCommand;
export type ToolOutcome = {
    notes: string[];
    forceAsk?: string;
    markCsp?: boolean;
};
/**
 * After-tool policy. Ordered private handlers = Chain of Responsibility inside
 * one aggregate so agent.ts does not own fail-streak / hard-deny / CSP.
 */
export declare class ToolOutcomePolicy {
    private readonly sameFailureLimit;
    private failKey;
    private failCount;
    constructor(sameFailureLimit: number);
    resetStreak(): void;
    onFailure(input: {
        tool: string;
        code: string;
        message: string;
        listHints: ListOpenHint[];
        locale?: string;
    }): ToolOutcome;
}
export declare function transportAskQuestion(message: string, locale?: string): string;
