import type { AgentCtx } from './agent-ctx.js';
/** Trace marker: this run is driven by the Pi-shaped loop, not the old inline loop. */
export declare const PI_LOOP_NOTE = "LOOP: pi runLoop (prepareNextTurn \u2192 steer \u2192 one tool)";
/**
 * Build PAGE STATE from current snap + friction; inject into ctx and trace.
 * Idempotent for a given (url, snapshot revision): several call sites invoke
 * this defensively (run start, PreflightHook, after a click) and when
 * nothing has changed the page since the last call there is nothing new to
 * compute — recomputing anyway just re-emits an identical PAGE STATE note,
 * doubling prompt tokens and ledger noise for no new information.
 */
export declare function attachPageState(ctx: AgentCtx): Promise<void>;
/**
 * Pi `prepareNextTurn`: after navigation, wait until the page is stable,
 * refresh the snapshot, then inject PAGE STATE for the next model turn.
 */
export declare function prepareNextTurn(ctx: AgentCtx): Promise<void>;
