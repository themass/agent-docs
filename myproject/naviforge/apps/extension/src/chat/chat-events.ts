import type { TraceMeta } from '@naviforge/runtime'
import type { TraceRecord } from '@naviforge/session'

import type { LocaleId } from '../i18n/locales'
import { recordViews, isContextView, type RecordView } from '../lib/agent-event-projection'

/** Restore / live timeline: same `viewRecord`. Telemetry stays off the chat list. */
export function sessionToChatEvents(records: TraceRecord[], locale?: LocaleId): RecordView[] {
  return recordViews(records, locale)
}

export function partitionChildTraceViews(events: RecordView[]): {
  main: RecordView[]
  childrenByParent: Map<string, RecordView[]>
} {
  const main: RecordView[] = []
  const childrenByParent = new Map<string, RecordView[]>()
  for (const event of events) {
    if (event.parentRunId) {
      const bucket = childrenByParent.get(event.parentRunId) ?? []
      bucket.push(event)
      childrenByParent.set(event.parentRunId, bucket)
    } else {
      main.push(event)
    }
  }
  return { main, childrenByParent }
}

export type TraceGroup<T> = TraceMeta & { parentRunId?: string; items: T[] }

/**
 * Split a flat trace into consecutive runs belonging to the same turn of the same task,
 * so the timeline shows the loop's own structure instead of one long list of cards.
 *
 * Entries without a turn (setup, deterministic work, local notes) stay ungrouped.
 */
export function groupByTurn<T extends TraceMeta>(items: T[]): TraceGroup<T>[] {
  const groups: TraceGroup<T>[] = []
  for (const item of items) {
    const last = groups.at(-1)
    if (
      item.turn !== undefined &&
      last?.turn === item.turn &&
      last.taskId === item.taskId &&
      last.parentRunId === item.parentRunId &&
      last.runId === item.runId
    ) {
      last.items.push(item)
    } else {
      groups.push({ runId: item.runId, taskId: item.taskId, turn: item.turn, parentRunId: item.parentRunId, items: [item] })
    }
  }
  return groups
}

/**
 * What the agent was trying to achieve in a turn, phrased as something re-runnable.
 *
 * Replaying the turn's action is unsound — the page has moved on since, so the recorded
 * click targets an index that may no longer mean anything. The intent survives that drift,
 * so re-running a step means queueing its goal and letting the model decide again.
 */
export function turnIntent(group: TraceGroup<RecordView>): string | null {
  const step = group.items.find((event) => event.variant === 'step')
  return step?.body.trim() || null
}

const ACTION_VARIANTS = new Set<string>(['tool', 'error', 'success', 'network'])

export function isAgentStepGroup(group: TraceGroup<RecordView>): boolean {
  return (
    group.turn !== undefined &&
    group.items.some((event) => event.variant === 'step' || ACTION_VARIANTS.has(event.variant))
  )
}

export type ReflectionLine = { tone: 'done' | 'plan' | 'note'; text: string }

/** Markdown / multi-paragraph model dump — that's the answer, not a plan line. */
export function looksLikeAnswer(body: string): boolean {
  const text = body.trim()
  if (!text) return false
  if (/^#{1,3}\s/m.test(text)) return true
  return text.split('\n').filter((line) => line.trim()).length >= 5
}

function isDonePlan(event: RecordView): boolean {
  return event.variant === 'step' && (/system[._]done/.test(event.meta ?? '') || looksLikeAnswer(event.body))
}

/** Split a turn's plan into the short checkpoint lines a step card shows. */
export function reflectionLines(items: RecordView[]): ReflectionLine[] {
  const lines: ReflectionLine[] = []
  for (const event of items) {
    if (event.variant !== 'step') continue
    if (!isDonePlan(event) && !looksLikeAnswer(event.body)) {
      for (const part of event.body.split(/[；;\n]+/)) {
        const text = part.trim()
        if (text) lines.push({ tone: 'done', text })
      }
    }
    if (!event.meta) continue
    for (const part of event.meta.split(' · ')) {
      const text = part.trim()
      if (!text) continue
      if (/^下一步：system[._]done$/.test(text)) continue
      if (text.startsWith('原因：')) {
        const reason = text.slice(3).trim()
        if (!reason || reason === 'done' || reason === '完成') continue
        lines.push({ tone: 'plan', text: reason })
        continue
      }
      lines.push({ tone: 'note', text })
    }
  }
  return lines
}

export function turnActions(items: RecordView[]): RecordView[] {
  return items.filter((event) => ACTION_VARIANTS.has(event.variant))
}

export function turnTimings(
  items: RecordView[],
  prevAt?: number
): { thinkMs: number; actMs: number; startedAt: number } {
  const first = items[0]?.at ?? 0
  const planAt = items.find((event) => event.variant === 'step')?.at ?? first
  const last = items.at(-1)?.at ?? planAt
  // ponytail: planning status is not rendered, so think starts at the previous
  // group's last timestamp (usually the prior tool or the user task).
  const thinkStart = prevAt ?? planAt
  return {
    thinkMs: Math.max(0, planAt - thinkStart),
    actMs: Math.max(0, last - planAt),
    startedAt: planAt,
  }
}

export function formatDurationMs(ms: number): string {
  if (ms < 1000) return `${Math.max(0, Math.round(ms))}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function turnDoneLabel(items: RecordView[]): { ok: boolean; tool: string } | null {
  const action = [...items].reverse().find((event) => ACTION_VARIANTS.has(event.variant))
  if (!action) return null
  return { ok: action.variant !== 'error', tool: action.title }
}

/** The user-facing answer in a turn, if this turn finished the task. */
export function turnAnswer(items: RecordView[]): RecordView | null {
  const io = items.find((event) => event.variant === 'step' && (event.request || event.response))
  const withIo = (event: RecordView): RecordView =>
    io ? { ...event, request: event.request || io.request, response: event.response || io.response } : event
  const result = items.find((event) => event.variant === 'result')
  if (result?.body.trim()) return withIo(result)
  if (turnActions(items).length) return null
  const step = items.find((event) => isDonePlan(event) && event.body.trim())
  return step ? withIo({ ...step, variant: 'result', title: '结果' }) : null
}

/** Tool/plan rows to keep on the step card — not the final answer. */
export function turnProcessItems(items: RecordView[]): RecordView[] {
  return items.filter((event) => event.variant !== 'result' && !isDonePlan(event))
}

const IDLE_DONE =
  /等待新任务|等下一个任务|没有待执行|上一个任务已完成|已输出完毕|仍在运行，上/

/** A follow-up turn that only narrates "already done, waiting". */
export function isIdleDoneTurn(items: RecordView[]): boolean {
  if (turnActions(items).length) return false
  const text = `${turnAnswer(items)?.body ?? ''} ${items.find((event) => event.variant === 'step')?.body ?? ''}`
  return IDLE_DONE.test(text)
}

function unique(items: string[]): string[] {
  return [...new Set(items.map((item) => item.trim()).filter(Boolean))]
}

export type RunTrace = { thoughts: string[]; tools: string[]; skills: string[] }

/** Tools / skills / short thoughts from the run, to pin above the answer. */
export function collectRunTrace(events: RecordView[]): RunTrace {
  const thoughts: string[] = []
  const tools: string[] = []
  const skills: string[] = []
  for (const event of events) {
    if (event.variant === 'step' && !looksLikeAnswer(event.body) && !isDonePlan(event)) {
      const line = event.body.split(/[；;\n]/)[0]?.trim() ?? ''
      if (line && line.length <= 120) thoughts.push(line)
    }
    if (event.variant === 'tool' || event.variant === 'success') {
      if (event.title === 'skill_load' || event.title.startsWith('skill.')) {
        const fromJson = /"id"\s*:\s*"([^"]+)"/.exec(event.request ?? event.meta ?? '')?.[1]
        const fromBody = /# skill:([^\s@]+)/.exec(event.body)?.[1]
        skills.push(fromJson ?? fromBody ?? event.body.slice(0, 40))
      } else {
        tools.push(event.title)
      }
    }
    const mentioned = /Skill：\s*([^\n]+)/.exec(event.body)
    if (mentioned) {
      for (const name of mentioned[1]!.split(/[,，]/)) skills.push(name.trim())
    }
  }
  return {
    thoughts: unique(thoughts).slice(-3),
    tools: unique(tools),
    skills: unique(skills),
  }
}

export function navigatedUrl(event: RecordView): string | null {
  const blob = [event.title, event.meta, event.body, event.request, event.response]
    .filter(Boolean)
    .join('\n')
  const looksNav =
    /navigate|open_new_tab|tabs\.(open|create)|dom\.goto|browser\.goto/i.test(event.title) ||
    /page navigated|navigated to|opened new tab/i.test(blob)
  if (!looksNav) return null
  const match = /https?:\/\/[^\s"'<>\\]+/.exec(blob)
  return match?.[0]?.replace(/[),.;]+$/, '') ?? null
}

export function collapseChatEvents(events: RecordView[]): RecordView[] {
  const out: RecordView[] = []
  for (const event of events) {
    const prev = out[out.length - 1]
    if (event.repeatKey && prev?.repeatKey === event.repeatKey) {
      out[out.length - 1] = {
        ...prev,
        at: event.at,
        repeat: (prev.repeat ?? 1) + 1,
        body: event.body,
        meta: event.meta ?? prev.meta,
        request: event.request ?? prev.request,
        response: event.response ?? prev.response,
      }
      continue
    }
    out.push({ ...event, repeat: undefined })
  }
  return out
}

/** Keep the context card when a long live view would slice it off. */
export function capChatEvents(events: RecordView[], max = 100): RecordView[] {
  if (events.length <= max) return events
  const pinned = events.filter((event) => isContextView(event))
  const room = Math.max(0, max - pinned.length)
  const rest = events.filter((event) => !isContextView(event)).slice(-room)
  const keep = new Set(rest.map((event) => event.id))
  for (const event of pinned) keep.add(event.id)
  return events.filter((event) => keep.has(event.id))
}
