/** Portable, canonical run record. */
export const TRACE_SCHEMA = 1 as const

export type TraceChannel = 'conversation' | 'trace' | 'telemetry'

export type TraceRecordType =
  | 'user.task'
  | 'user.steer'
  | 'run.context'
  | 'run.tools'
  | 'run.mode'
  | 'model.turn'
  | 'tool.result'
  | 'run.result'
  | 'run.ask'
  | 'run.recovery'
  | 'run.error'
  | 'run.network'
  | 'run.note'
  | 'context.compaction'
  | 'run.log'
  | 'metrics.tokens'
  | 'metrics.context'
  | 'intake.question'
  | 'intake.answer'
  | 'intake.complete'
  | 'artifact.saved'

export type TraceRecordPayload = {
  'user.task': {
    text: string
    imageDataUrl?: string
    imageLabel?: string
    audioPath?: string
    audioLabel?: string
    /** Live playback only. Do not persist this on disk / chrome.storage. */
    audioDataUrl?: string
  }
  'user.steer': { texts: string[]; phase: 'pre_model' | 'abort_tool' }
  'run.context': {
    systemPrompt: string
    tools: string[]
    taskMode?: 'in_page' | 'research' | 'general' | 'list_detail'
    skills?: string[]
    skillGuidance?: string
    mcpTools?: Array<{ name: string; description?: string; serverId: string; tool: string }>
    mcpNote?: string
  }
  'run.tools': {
    catalog: Array<{
      name: string
      description: string
      source?: 'builtin' | 'mcp'
    }>
  }
  'run.mode': { mode: 'deterministic' | 'model'; detail: string }
  'model.turn': {
    status: string
    summary: string
    reason?: string
    call?: { tool: string; arguments: Record<string, unknown> }
    io?: {
      user: string
      assistant: string
      reasoning?: string
      toolCalls?: Array<{ name: string; arguments: Record<string, unknown> }>
      hasImage?: boolean
    }
  }
  'tool.result': {
    tool: string
    arguments: Record<string, unknown>
    ok: boolean
    data?: unknown
    error?: { code: string; message: string; recoverable?: boolean }
  }
  'run.result': { text: string }
  'run.ask': { question: string; wait: 'user' | 'captcha' | 'intake' }
  'run.recovery': {
    strategy: string
    diagnostic: string
    tool?: string
    code?: string
    question?: string
    from?: string
    to?: string
  }
  'run.error': { message: string; code?: string; tool?: string }
  'run.network': { attached: boolean; message: string }
  'run.note': { text: string; topic?: string }
  'context.compaction': {
    summary: string
    coveredRecordIds: string[]
    coveredRange?: { from: string; to: string }
    preservedConstraints: string[]
    openWork: string[]
    tokenUsage: number
    /** `llm` = semantic summary call; `deterministic` = template fallback. */
    mode?: 'deterministic' | 'llm'
  }
  'run.log': { message: string }
  'metrics.tokens': { prompt: number; completion: number; total: number; runTotal: number }
  'metrics.context': {
    turn?: number
    breakdown: {
      limitInputTokens: number
      runTokenBudget: number
      runTotalTokens: number
      systemTokens: number
      blocks: Array<{ id: string; label: string; chars: number; tokens: number }>
      userTotalTokens: number
      grandTotalTokens: number
      pressured: boolean
      compaction?: { beforeTokens: number; afterTokens: number; coveredRecords: number }
    }
  }
  'intake.question': { round: number; questions: Array<Record<string, unknown>> }
  'intake.answer': {
    round: number
    answers: Record<string, string | string[]>
    freeText?: string
    questions?: Array<Record<string, unknown>>
  }
  'intake.complete': { summary: string; assumptions: string[]; roundCount: number }
  'artifact.saved': { kind: 'shot'; path: string; tool: string }
}

export type TraceRecord = {
  schema: typeof TRACE_SCHEMA
  id: string
  at: number
  runId: string
  parentRunId?: string
  taskId?: string
  turn?: number
  channel: TraceChannel
} & {
  [Type in TraceRecordType]: {
    type: Type
    payload: TraceRecordPayload[Type]
  }
}[TraceRecordType]

export type SessionStatus = 'running' | 'waiting' | 'success' | 'failed' | 'cancelled'

/** `thread` = user-continuable main run; `leaf` = spawn child, audit-only, not resumable. */
export type SessionKind = 'thread' | 'leaf'

/** One agent run audit envelope (persisted snapshot). */
export type SessionSnapshot = {
  id: string
  kind?: SessionKind
  threadId?: string
  /** Set on leaf sessions — links to the parent thread run session. */
  parentSessionId?: string
  /** Trace parent run id (spawn caller). */
  parentRunId?: string
  /** Child trace run id (unique per leaf). */
  leafRunId?: string
  playbookId?: string
  task: string
  status: SessionStatus
  createdAt: number
  updatedAt: number
  page?: { tabId: number; url?: string; title?: string }
  records: TraceRecord[]
}

export type ThreadMemory = {
  goal: string
  facts: string[]
  constraints: string[]
  openQuestions: string[]
  lastOutcome: string
}

/** Cross-run conversation container. */
export type Thread = {
  id: string
  title: string
  memory: ThreadMemory
  lastPlaybookId?: string
  /** Timestamp of the newest run represented by `memory`. */
  memoryAt?: number
  createdAt: number
  updatedAt: number
}

export type SessionAuditExport = {
  schemaVersion: 1
  exportedAt: number
  threads: Thread[]
  sessions: SessionSnapshot[]
}

export type RunPhase =
  | 'idle'
  | 'preflight'
  | 'intake'
  | 'running'
  | 'waiting_user'
  | 'paused'
  | 'compacting'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type SessionEvent =
  | { type: 'record'; record: TraceRecord }
  | { type: 'phase'; phase: RunPhase }
  | { type: 'queue'; steering: number; followUp: number }
