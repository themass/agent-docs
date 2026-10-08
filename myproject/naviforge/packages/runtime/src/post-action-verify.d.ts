/**
 * Generic "did this click actually do anything" check.
 *
 * Runtime problem this solves: a model (or a deterministic candidate-click
 * helper) can click a DOM index that *looks* like a card/tile and treat the
 * click as progress, even when the page did not change at all (dead
 * element, overlay no-op, SPA swallowed the event). Without this, callers
 * either (a) wrongly assume the click opened a detail view and move on to
 * read evidence that never materialized, or (b) retry the exact same
 * useless index forever.
 *
 * This module is deliverable-agnostic: it only knows about URL, DOM
 * snapshot revision, Page State items, and Network event counts. Any task
 * that performs a click-and-check flow (media, forms, pagination, …) can
 * reuse it. No site/domain-specific logic belongs here.
 */
import type { AgentCtx } from './agent-ctx.js';
export type ActionBaseline = {
    url: string;
    revision: number;
    itemKeys: Set<string>;
    networkEventCount: number;
};
export type ActionVerification = {
    urlChanged: boolean;
    revisionChanged: boolean;
    newCandidatesFound: boolean;
    networkActivityObserved: boolean;
    /** True when none of the above changed — the action was very likely a no-op. */
    noEffect: boolean;
};
/** Snapshot the state we need to diff *before* performing a click. */
export declare function captureActionBaseline(ctx: AgentCtx): Promise<ActionBaseline>;
/**
 * Compare current ctx state against a baseline captured before the action.
 * Caller is responsible for re-snapshotting DOM and re-running
 * `attachPageState` first (see `clickAndVerify` for the common path).
 */
export declare function verifyActionEffect(ctx: AgentCtx, baseline: ActionBaseline): Promise<ActionVerification>;
/** Stable key for "have we already tried clicking this index on this page and seen nothing happen". */
export declare function inertCandidateKey(url: string, index: number): string;
export declare function isKnownInertCandidate(ctx: AgentCtx, url: string, index: number): boolean;
export declare function markInertCandidate(ctx: AgentCtx, url: string, index: number): void;
export type ClickAndVerifyOptions = {
    /** Snapshot index to click. */
    index: number;
    /** Extra settle wait after click, before re-snapshot (ms). Default: rely on dom.wait network_idle. */
    waitTimeoutMs?: number;
};
export type ClickAndVerifyResult = {
    ok: true;
    verification: ActionVerification;
} | {
    ok: false;
    reason: 'already_inert' | 'click_failed' | 'dom_unavailable';
    message?: string;
};
/**
 * Generic click-then-verify primitive: click a snapshot index, let the page
 * settle, re-snapshot, rebuild Page State, then diff against the
 * pre-click baseline. Marks the candidate as inert (so callers should not
 * retry the same index on the same URL) when nothing observably changed.
 *
 * Does not know what the caller is trying to achieve — it only reports
 * whether the click had any observable effect. Callers (e.g. the media
 * candidate harvester) decide what to do next (try a different candidate,
 * look for a secondary play control, ask the model to replan, etc).
 */
export declare function clickAndVerify(ctx: AgentCtx, opts: ClickAndVerifyOptions): Promise<ClickAndVerifyResult>;
