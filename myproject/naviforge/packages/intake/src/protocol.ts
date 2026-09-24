import type { ClarificationQuestion, IntakeAnswerMap } from './types.js'
import { MAX_QUESTIONS_PER_ROUND } from './types.js'
import type { IntakeMode } from './types.js'

/**
 * Whether to bypass the intake phase entirely.
 * `auto` / `always` always enter intake — the model decides clarify vs begin_task there.
 */
export function shouldSkipIntake(task: string, mode: IntakeMode): boolean {
  if (mode === 'off') return true
  return !task.trim()
}

export function normalizeClarificationQuestions(raw: unknown): ClarificationQuestion[] {
  if (!Array.isArray(raw)) return []
  const out: ClarificationQuestion[] = []
  for (const item of raw.slice(0, MAX_QUESTIONS_PER_ROUND)) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const id = typeof row.id === 'string' ? row.id.trim() : ''
    const prompt = typeof row.prompt === 'string' ? row.prompt.trim() : ''
    const kind =
      row.kind === 'multi' || row.kind === 'text' || row.kind === 'single' ? row.kind : 'single'
    if (!id || !prompt) continue
    const options = Array.isArray(row.options)
      ? row.options
          .map((opt) => {
            if (!opt || typeof opt !== 'object') return null
            const o = opt as Record<string, unknown>
            const oid = typeof o.id === 'string' ? o.id.trim() : ''
            const label = typeof o.label === 'string' ? o.label.trim() : ''
            if (!oid || !label) return null
            return {
              id: oid,
              label,
              description: typeof o.description === 'string' ? o.description : undefined,
            }
          })
          .filter((opt): opt is NonNullable<typeof opt> => Boolean(opt))
      : undefined
    out.push({
      id,
      prompt,
      kind,
      options: options?.length ? options : undefined,
      required: row.required !== false,
      defaultOptionId: typeof row.defaultOptionId === 'string' ? row.defaultOptionId : undefined,
    })
  }
  return out
}

export function parseIntakeAnswerJson(text: string): IntakeAnswerMap | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  try {
    const parsed = JSON.parse(trimmed) as unknown
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null
    const out: IntakeAnswerMap = {}
    for (const [key, value] of Object.entries(parsed)) {
      if (typeof value === 'string') out[key] = value
      else if (Array.isArray(value) && value.every((v) => typeof v === 'string')) out[key] = value
    }
    return Object.keys(out).length ? out : null
  } catch {
    return { _freeText: trimmed }
  }
}

/** Human-readable prompt for HITL / UI (not machine JSON). */
export function summarizeIntakeAsk(questions: ClarificationQuestion[]): string {
  if (questions.length === 1) return questions[0]!.prompt
  return questions.map((q, i) => `${i + 1}. ${q.prompt}`).join('\n')
}

/** User-facing summary of submitted intake answers (timeline / bubbles). */
export function formatIntakeAnswerSummary(
  questions: ClarificationQuestion[],
  answers: IntakeAnswerMap
): string {
  const lines: string[] = []
  for (const question of questions) {
    const answer = answers[question.id]
    if (answer == null) continue
    const renderValue = (value: string): string => {
      const option = question.options?.find((opt) => opt.id === value)
      return option?.label ?? value
    }
    const rendered = Array.isArray(answer)
      ? answer.map((value) => renderValue(value)).join(', ')
      : renderValue(String(answer))
    lines.push(`${question.prompt}: ${rendered}`)
  }
  const free =
    typeof answers._freeText === 'string'
      ? answers._freeText.trim()
      : ''
  if (free && !lines.some((line) => line.includes(free))) lines.push(free)
  return lines.join('\n') || free || '已确认'
}

export function formatIntakeConstraints(
  questions: ClarificationQuestion[],
  answers: IntakeAnswerMap
): string[] {
  const lines: string[] = []
  for (const question of questions) {
    const answer = answers[question.id] ?? answers._freeText
    if (answer == null) continue
    const renderValue = (value: string): string => {
      const option = question.options?.find((opt) => opt.id === value)
      return option?.label ?? value
    }
    const rendered = Array.isArray(answer)
      ? answer.map((value) => renderValue(value)).join(', ')
      : renderValue(String(answer))
    lines.push(`CLARIFICATION: ${question.prompt} → ${rendered}`)
  }
  return lines
}
