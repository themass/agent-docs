import type { TraceRecord } from './types.js'
import type { Thread } from './types.js'
import { formatThreadMemory } from './thread-memory.js'

export type ThreadReuse = {
  skillIds: string[]
  page?: {
    url: string
    evidence: string
  }
}

export type ThreadContext = {
  memory: string
  conversation: string
  reuse: ThreadReuse
}

const PAGE_EVIDENCE_CHARS = 3_000
const DIALOGUE_CHAR_BUDGET = 10_000
const USER_CHAR_LIMIT = 900
const RESULT_CHAR_LIMIT = 2_400

function clip(text: string, limit: number): string {
  const trimmed = text.trim()
  if (trimmed.length <= limit) return trimmed
  return `${trimmed.slice(0, limit)}…`
}

/** Human-readable dialogue for THREAD block (Hermes slots + pi-style prior turns). */
function dialogueLine(rec: TraceRecord): string | null {
  if (rec.type === 'user.task') {
    const text = typeof rec.payload.text === 'string' ? rec.payload.text : ''
    return text.trim() ? `user: ${clip(text, USER_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'user.steer') {
    const texts = Array.isArray(rec.payload.texts)
      ? rec.payload.texts.filter((item): item is string => typeof item === 'string')
      : []
    const joined = texts.join(' · ').trim()
    return joined ? `steer: ${clip(joined, USER_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'run.result') {
    const text = typeof rec.payload.text === 'string' ? rec.payload.text : ''
    return text.trim() ? `assistant: ${clip(text, RESULT_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'run.ask') {
    const q = typeof rec.payload.question === 'string' ? rec.payload.question : ''
    return q.trim() ? `assistant (ask): ${clip(q, USER_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'run.error') {
    const msg = typeof rec.payload.message === 'string' ? rec.payload.message : ''
    return msg.trim() ? `error: ${clip(msg, USER_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'run.recovery') {
    const diag = typeof rec.payload.diagnostic === 'string' ? rec.payload.diagnostic : ''
    return diag.trim()
      ? `recovery (${rec.payload.strategy}): ${clip(diag, USER_CHAR_LIMIT)}`
      : null
  }
  if (rec.type === 'context.compaction') {
    const summary = typeof rec.payload.summary === 'string' ? rec.payload.summary : ''
    return summary.trim() ? `compaction: ${clip(summary, RESULT_CHAR_LIMIT)}` : null
  }
  if (rec.type === 'intake.complete') {
    const summary = typeof rec.payload.summary === 'string' ? rec.payload.summary : ''
    return summary.trim() ? `intake: ${clip(summary, USER_CHAR_LIMIT)}` : null
  }
  return null
}

function buildConversation(messages: TraceRecord[]): string {
  const lines = messages
    .map(dialogueLine)
    .filter((line): line is string => Boolean(line))
  let total = 0
  const kept: string[] = []
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const line = lines[index]!
    if (kept.length && total + line.length + 1 > DIALOGUE_CHAR_BUDGET) break
    kept.unshift(line)
    total += line.length + 1
  }
  return kept.join('\n') || '(none)'
}

function toolFields(rec: TraceRecord): { tool: string; data?: Record<string, unknown> } | null {
  if (rec.type !== 'tool.result') return null
  const payload = rec.payload
  const data =
    payload.ok && payload.data && typeof payload.data === 'object' && !Array.isArray(payload.data)
      ? (payload.data as Record<string, unknown>)
      : undefined
  return { tool: payload.tool, data }
}

/** Last read_page + skill.load ids in this thread. */
export function formatSessionReuse(messages: TraceRecord[]): ThreadReuse {
  let pageUrl = ''
  let pageText = ''
  const skillIds: string[] = []
  for (const message of messages) {
    const fields = toolFields(message)
    if (!fields) continue
    if (fields.tool === 'dom_read') {
      const text = typeof fields.data?.text === 'string' ? fields.data.text : ''
      if (text.trim()) {
        pageText = text
        pageUrl = typeof fields.data?.url === 'string' ? fields.data.url : pageUrl
      }
    }
    if (fields.tool === 'skill_load') {
      const id = typeof fields.data?.id === 'string' ? fields.data.id : undefined
      if (id && id !== 'page-read@skipped' && !skillIds.includes(id)) skillIds.push(id)
    }
  }
  return {
    skillIds,
    page:
      pageUrl && pageText.trim()
        ? { url: pageUrl, evidence: pageText.trim().slice(0, PAGE_EVIDENCE_CHARS) }
        : undefined,
  }
}

/** Bounded context for the next run (Hermes slots + pi-style prior dialogue). */
export function buildThreadContext(thread: Thread, messages: TraceRecord[]): ThreadContext {
  const dialogueTypes = new Set<TraceRecord['type']>([
    'user.task',
    'user.steer',
    'run.result',
    'run.error',
    'run.recovery',
    'run.ask',
    'context.compaction',
    'intake.complete',
  ])
  const dialogueRecords = messages.filter((message) => dialogueTypes.has(message.type))
  return {
    memory: formatThreadMemory(thread.memory) || '(none)',
    conversation: buildConversation(dialogueRecords),
    reuse: formatSessionReuse(messages),
  }
}
