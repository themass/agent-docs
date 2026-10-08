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
/** Before executing: allow, skip (hint only), or stop the run. */
export declare function decideActionLoop(gate: ActionLoopGate, key: string | null): 'allow' | 'skip' | 'stop';
export declare function recordActionLoopSuccess(gate: ActionLoopGate, key: string | null): void;
export type ActionLoopCall = {
    tool: string;
    arguments?: Record<string, unknown>;
};
/** Replay successful calls on one URL. `stopAt` is the call index that would halt the run, or -1. */
export declare function replayActionLoop(calls: ActionLoopCall[], url: string, limit?: 2): {
    stopAt: number;
    allowed: number;
};
