import type { TraceRecord } from './types.js'
import {
  formatIntakeAnswerForTrace,
  formatIntakeAskForTrace,
  normalizeTraceIntakeQuestions,
} from './intake-trace-format.js'

/** Render-only projection from canonical `TraceRecord`. Never persisted. */
export type TraceView = {
  id: string
  at: number
  runId?: string
  parentRunId?: string
  taskId?: string
  turn?: number
  variant: string
  title: string
  body: string
  meta?: string
  request?: string
  response?: string
  imageDataUrl?: string
  imageLabel?: string
  audioDataUrl?: string
  audioPath?: string
  repeatKey?: string
  repeat?: number
  /** Render-only: tools[] snapshot for this run (audit / UI only). */
  toolCatalog?: Array<{ name: string; description: string; source?: 'builtin' | 'mcp' }>
}

const text = (value: unknown): string => (typeof value === 'string' ? value : JSON.stringify(value) ?? '')
const clip = (value: unknown, max = 600): string => {
  const raw = text(value)
  return raw.length > max ? `${raw.slice(0, max)}…` : raw
}
const pretty = (value: unknown): string => {
  try {
    return JSON.stringify(value, null, 2) ?? ''
  } catch {
    return text(value)
  }
}

export function projectTraceView(record: TraceRecord): TraceView | null {
  const base = {
    id: record.id,
    at: record.at,
    runId: record.runId,
    parentRunId: record.parentRunId,
    taskId: record.taskId,
    turn: record.turn,
  }
  switch (record.type) {
    case 'user.task':
      return {
        ...base,
        variant: 'task',
        title: 'Task',
        body: record.payload.text,
        imageDataUrl: record.payload.imageDataUrl,
        imageLabel: record.payload.imageLabel,
        audioDataUrl: record.payload.audioDataUrl,
        audioPath: record.payload.audioPath,
      }
    case 'user.steer':
      return {
        ...base,
        variant: 'control',
        title: record.payload.phase === 'abort_tool' ? 'Steer (abort tool)' : 'Steer',
        body: record.payload.texts.join('\n'),
      }
    case 'run.context':
      // Audit-only: system prompt lives in session JSONL, not the user timeline.
      return null
    case 'run.tools': {
      const catalog = record.payload.catalog
      if (!catalog.length) return null
      return {
        ...base,
        variant: 'tools',
        title: 'Tools',
        body: '',
        meta: String(catalog.length),
        toolCatalog: catalog,
      }
    }
    case 'run.mode':
      return {
        ...base,
        variant: 'system',
        title: record.payload.mode === 'model' ? 'Model mode' : 'Deterministic mode',
        body: record.payload.detail,
      }
    case 'model.turn': {
      const io = record.payload.io
      return {
        ...base,
        variant: 'step',
        title: record.payload.call ? 'Plan' : record.payload.status === 'done' ? 'Done' : 'Think',
        body: record.payload.summary,
        meta: record.payload.reason,
        request: io?.user,
        response: io
          ? [io.reasoning, io.assistant, io.toolCalls?.length ? pretty(io.toolCalls) : '']
              .filter(Boolean)
              .join('\n\n')
          : undefined,
      }
    }
    case 'tool.result':
      return {
        ...base,
        variant: record.payload.ok ? 'tool' : 'error',
        title: record.payload.tool,
        body: record.payload.ok
          ? clip(record.payload.data) || 'ok'
          : (record.payload.error?.message ?? 'failed'),
        meta: clip(record.payload.arguments, 120),
        request: pretty(record.payload.arguments),
        response: record.payload.ok ? pretty(record.payload.data) : record.payload.error?.message,
        repeatKey: `tool:${record.payload.tool}`,
      }
    case 'run.result':
      return { ...base, variant: 'result', title: 'Result', body: record.payload.text }
    case 'run.ask':
      if (record.payload.wait === 'intake') return null
      return {
        ...base,
        variant: 'question',
        title: 'Question',
        body: record.payload.question,
        meta: record.payload.wait === 'captcha' ? 'captcha' : undefined,
      }
    case 'run.recovery':
      return {
        ...base,
        variant: 'recovery',
        title: 'Recovery',
        body: record.payload.diagnostic,
        meta: record.payload.strategy,
      }
    case 'run.error':
      return {
        ...base,
        variant: 'error',
        title: record.payload.code === 'blocked' ? 'Blocked' : 'Failed',
        body: record.payload.message,
      }
    case 'run.network':
      return record.payload.attached
        ? { ...base, variant: 'network', title: 'Network', body: record.payload.message }
        : null
    case 'run.note':
      return {
        ...base,
        variant: 'system',
        title: record.payload.topic ?? 'Note',
        body: record.payload.text,
      }
    case 'context.compaction':
      return {
        ...base,
        variant: 'system',
        title: 'Compaction',
        body: record.payload.summary,
        meta: `${record.payload.mode ?? 'deterministic'} · ${record.payload.coveredRecordIds.length} records · ${record.payload.tokenUsage} tokens`,
      }
    case 'metrics.context': {
      const breakdown = record.payload.breakdown
      const blocks = breakdown.blocks
        .slice(0, 4)
        .map((block) => `${block.label} ${block.tokens}`)
        .join(' · ')
      return {
        ...base,
        variant: 'system',
        title: 'Context usage',
        body: `${breakdown.grandTotalTokens}/${breakdown.limitInputTokens} tokens`,
        meta: blocks,
      }
    }
    case 'intake.question': {
      const questions = normalizeTraceIntakeQuestions(record.payload.questions)
      const body = formatIntakeAskForTrace(questions)
      if (!body) return null
      return {
        ...base,
        variant: 'question',
        title: 'Clarify',
        body,
        meta: questions.length > 1 ? `${questions.length} questions` : undefined,
      }
    }
    case 'intake.answer': {
      const questions = normalizeTraceIntakeQuestions(record.payload.questions)
      const body = questions.length
        ? formatIntakeAnswerForTrace(questions, record.payload.answers)
        : record.payload.freeText?.trim() ||
          Object.entries(record.payload.answers)
            .filter(([key]) => key !== '_freeText')
            .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : value}`)
            .join('\n') ||
          '已确认'
      return {
        ...base,
        variant: 'user',
        title: 'You',
        body,
      }
    }
    case 'intake.complete':
      return {
        ...base,
        variant: 'system',
        title: 'Intake complete',
        body: record.payload.summary,
        meta: record.payload.assumptions.join('; '),
      }
    case 'run.log':
    case 'metrics.tokens':
      return null
    case 'artifact.saved':
      return {
        ...base,
        variant: 'system',
        title: 'Artifact',
        body: record.payload.path,
        meta: record.payload.tool,
      }
  }
}

export function projectTraceViews(records: readonly TraceRecord[]): TraceView[] {
  return records.flatMap((record) => {
    const view = projectTraceView(record)
    return view ? [view] : []
  })
}
