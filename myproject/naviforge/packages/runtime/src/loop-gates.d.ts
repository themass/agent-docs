export { bareSkillId, isGeneralTask, isPageReadTask, isResearchTask, requestedList, requestedTopN, resolveTaskMode, shouldHintListThenDetail, urlsMatchForReuse, type TaskMode, } from './task-classifier.js';
export type { ThreadContext, ThreadReuse } from '@naviforge/session';
export declare function observationDedupeKey(tool: string, url: string, args?: Record<string, unknown>): string | null;
/** Stable key for repeated successful actions on the same URL (screenshot/scroll loops). */
export declare function actionLoopKey(tool: string, url: string, args?: Record<string, unknown>): string | null;
export type ActionLoopGate = {
    exec: Map<string, number>;
    skip: Map<string, number>;
    limit: number;
};
export declare function createActionLoopGate(limit: number): ActionLoopGate;
/** Before executing: allow, soft skip, or replan (never ends the run alone). */
export declare function decideActionLoop(gate: ActionLoopGate, key: string | null): 'allow' | 'skip' | 'replan';
export declare function recordActionLoopSuccess(gate: ActionLoopGate, key: string | null): void;
export type ActionLoopCall = {
    tool: string;
    arguments?: Record<string, unknown>;
};
/** Replay successful calls on one URL. `replanAt`/`stopAt` = second over-limit index, or -1. */
export declare function replayActionLoop(calls: ActionLoopCall[], url: string, limit?: 2): {
    replanAt: number;
    stopAt: number;
    allowed: number;
};
