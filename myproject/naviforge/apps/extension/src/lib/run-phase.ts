import type { RunPhase } from '@naviforge/session'

/** Side-panel run status — single source for UI state machine strings. */
export const RUN_STATUS = {
  IDLE: 'IDLE',
  PREPARING: 'PREPARING',
  RUNNING: 'RUNNING',
  PLANNING: 'PLANNING',
  ACTING: 'ACTING',
  OBSERVING: 'OBSERVING',
  WAITING_USER: 'WAITING_USER',
  CLARIFYING: 'CLARIFYING',
  PAUSED: 'PAUSED',
  COMPLETED: 'COMPLETED',
  FAILED: 'FAILED',
  CANCELLED: 'CANCELLED',
  BLOCKED: 'BLOCKED',
  FOLLOW_UP: 'FOLLOW_UP',
} as const

export type WorkspaceRunStatus = (typeof RUN_STATUS)[keyof typeof RUN_STATUS]

const RUNNING_LIKE = new Set<WorkspaceRunStatus>([
  RUN_STATUS.RUNNING,
  RUN_STATUS.PLANNING,
  RUN_STATUS.ACTING,
  RUN_STATUS.OBSERVING,
  RUN_STATUS.FOLLOW_UP,
])

export function isWorkspaceRunning(status: WorkspaceRunStatus): boolean {
  return RUNNING_LIKE.has(status) || status === RUN_STATUS.PREPARING
}

export function isWorkspaceActive(status: WorkspaceRunStatus): boolean {
  return (
    isWorkspaceRunning(status) ||
    status === RUN_STATUS.WAITING_USER ||
    status === RUN_STATUS.CLARIFYING ||
    status === RUN_STATUS.PAUSED
  )
}

/** Map UI status to persisted session `RunPhase`. */
export function toSessionRunPhase(status: WorkspaceRunStatus): RunPhase {
  switch (status) {
    case RUN_STATUS.IDLE:
      return 'idle'
    case RUN_STATUS.PREPARING:
      return 'preflight'
    case RUN_STATUS.RUNNING:
    case RUN_STATUS.PLANNING:
    case RUN_STATUS.ACTING:
    case RUN_STATUS.OBSERVING:
    case RUN_STATUS.FOLLOW_UP:
      return 'running'
    case RUN_STATUS.WAITING_USER:
    case RUN_STATUS.CLARIFYING:
      return 'waiting_user'
    case RUN_STATUS.PAUSED:
      return 'paused'
    case RUN_STATUS.COMPLETED:
      return 'succeeded'
    case RUN_STATUS.FAILED:
    case RUN_STATUS.BLOCKED:
      return 'failed'
    case RUN_STATUS.CANCELLED:
      return 'cancelled'
    default:
      return 'idle'
  }
}

/** i18n key under `agent.status.*` (IDLE has no label — header hides chip). */
export function runStatusI18nKey(status: WorkspaceRunStatus): WorkspaceRunStatus | 'IDLE' {
  return status === RUN_STATUS.IDLE ? 'IDLE' : status
}
