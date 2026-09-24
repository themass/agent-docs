import type { ThreadMemory } from './types.js'

export const EMPTY_THREAD_MEMORY: ThreadMemory = {
  goal: '',
  facts: [],
  constraints: [],
  openQuestions: [],
  lastOutcome: '',
}

export const SLOT_LIMITS = {
  goal: 500,
  fact: 400,
  constraint: 300,
  question: 300,
  lastOutcome: 800,
  facts: 24,
  constraints: 12,
  openQuestions: 8,
} as const

function trim(text: string, max: number): string {
  return text.trim().slice(0, max)
}

function mergeUnique(existing: string[], incoming: string[], max: number, itemMax: number): string[] {
  const seen = new Set<string>()
  const merged: string[] = []
  for (const item of [...existing, ...incoming]) {
    const normalized = trim(item, itemMax)
    if (!normalized) continue
    const key = normalized.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(normalized)
  }
  return merged.slice(-max)
}

export function formatThreadMemory(memory: ThreadMemory, charCap = 6_000): string {
  const lines = [
    memory.goal ? `GOAL: ${memory.goal}` : '',
    memory.constraints.length ? `CONSTRAINTS:\n- ${memory.constraints.join('\n- ')}` : '',
    memory.facts.length ? `FACTS:\n- ${memory.facts.join('\n- ')}` : '',
    memory.openQuestions.length ? `OPEN QUESTIONS:\n- ${memory.openQuestions.join('\n- ')}` : '',
    memory.lastOutcome ? `LAST OUTCOME: ${memory.lastOutcome}` : '',
  ].filter(Boolean)
  const text = lines.join('\n\n')
  return charCap > 0 && text.length > charCap ? text.slice(0, charCap) : text
}

/** Length before the display cap — compaction should measure this. */
export function threadMemoryPressure(memory: ThreadMemory): number {
  return formatThreadMemory(memory, 0).length
}

export function deriveThreadSummary(memory: ThreadMemory, charCap = 6_000): string {
  return formatThreadMemory(memory, charCap)
}

export function parseThreadMemoryJson(text: string): ThreadMemory | null {
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start < 0 || end <= start) return null
  try {
    const raw = JSON.parse(text.slice(start, end + 1)) as Record<string, unknown>
    const asStrings = (value: unknown): string[] =>
      Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
    return {
      goal: typeof raw.goal === 'string' ? trim(raw.goal, SLOT_LIMITS.goal) : '',
      facts: asStrings(raw.facts).map((item) => trim(item, SLOT_LIMITS.fact)),
      constraints: asStrings(raw.constraints).map((item) => trim(item, SLOT_LIMITS.constraint)),
      openQuestions: asStrings(raw.open_questions ?? raw.openQuestions).map((item) =>
        trim(item, SLOT_LIMITS.question)
      ),
      lastOutcome:
        typeof raw.last_outcome === 'string'
          ? trim(raw.last_outcome, SLOT_LIMITS.lastOutcome)
          : typeof raw.lastOutcome === 'string'
            ? trim(raw.lastOutcome, SLOT_LIMITS.lastOutcome)
            : '',
    }
  } catch {
    return null
  }
}

export function mergeThreadMemory(prev: ThreadMemory, next: Partial<ThreadMemory>): ThreadMemory {
  return {
    goal: next.goal?.trim() ? trim(next.goal, SLOT_LIMITS.goal) : prev.goal,
    facts: mergeUnique(prev.facts, next.facts ?? [], SLOT_LIMITS.facts, SLOT_LIMITS.fact),
    constraints: mergeUnique(
      prev.constraints,
      next.constraints ?? [],
      SLOT_LIMITS.constraints,
      SLOT_LIMITS.constraint
    ),
    openQuestions: mergeUnique(
      prev.openQuestions,
      next.openQuestions ?? [],
      SLOT_LIMITS.openQuestions,
      SLOT_LIMITS.question
    ),
    lastOutcome: next.lastOutcome?.trim()
      ? trim(next.lastOutcome, SLOT_LIMITS.lastOutcome)
      : prev.lastOutcome,
  }
}

/** Cheap sync update after a run — no LLM. */
export function memoryPatchFromRun(opts: {
  task: string
  result: string
  mode?: string
  /** When false, keep existing GOAL slot (e.g. user follow-up is「继续」). */
  setGoal?: boolean
}): Partial<ThreadMemory> {
  const urls = opts.result.match(/https?:\/\/[^\s\]）)]+/g)?.slice(0, 8) ?? []
  const facts = [
    opts.mode ? `last_run_mode: ${opts.mode}` : '',
    ...urls.map((url) => `listed_url: ${url}`),
  ].filter(Boolean)
  return {
    ...(opts.setGoal !== false ? { goal: opts.task.slice(0, SLOT_LIMITS.goal) } : {}),
    lastOutcome: opts.result.slice(0, SLOT_LIMITS.lastOutcome),
    facts,
  }
}
