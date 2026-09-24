import { deriveThreadSummary } from '@naviforge/session'

export type {
  SessionSnapshot as AgentSession,
  TraceRecord,
  Thread as AgentThread,
  Thread,
  ThreadMemory,
} from '@naviforge/session'
export {
  capSessionRecords,
  deriveThreadSummary,
  formatAuditJsonl,
  redactSessionText,
  sortSessionsByRecent,
  validateTraceRecord,
  buildThreadContext,
  createThread,
  formatSessionReuse,
  EMPTY_THREAD_MEMORY,
  mergeThreadMemory,
  memoryPatchFromRun,
  parseThreadMemoryJson,
  threadMemoryPressure,
  SLOT_LIMITS,
  isContinuationMessage,
  extractOriginalTaskFromRecords,
  sessionDisplayTitle,
} from '@naviforge/session'

export function threadSummaryFromMemory(
  memory: import('@naviforge/session').ThreadMemory
): string {
  return deriveThreadSummary(memory)
}
