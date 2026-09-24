export const BEHAVIOR_RECORD = 'BEHAVIOR_RECORD' as const

export type BehaviorRecordMessage =
  | { type: typeof BEHAVIOR_RECORD; action: 'start'; tabId: number }
  | { type: typeof BEHAVIOR_RECORD; action: 'stop' }
  | { type: typeof BEHAVIOR_RECORD; action: 'status' }
  | { type: typeof BEHAVIOR_RECORD; action: 'batch'; sessionId: string; events: unknown[] }
  | { type: typeof BEHAVIOR_RECORD; action: 'rrweb_batch'; sessionId: string; events: unknown[] }
  | { type: typeof BEHAVIOR_RECORD; action: 'list' }
  | { type: typeof BEHAVIOR_RECORD; action: 'get'; sessionId: string }
  | { type: typeof BEHAVIOR_RECORD; action: 'delete'; sessionId: string }
