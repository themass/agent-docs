/**
 * 可注入的时间源。房间逻辑不直接调用 Date.now()，
 * 因此「20 秒到点」这类行为能被确定性测试（见 Task 8 的设计约束）。
 */
export type Clock = { now(): number }

export const systemClock: Clock = { now: () => Date.now() }
