/** Trace-only intake formatting — keeps @naviforge/session free of @naviforge/intake for WXT/Vite. */

type TraceIntakeOption = { id: string; label: string }
type TraceIntakeQuestion = {
  id: string
  prompt: string
  options?: TraceIntakeOption[]
}

export function normalizeTraceIntakeQuestions(raw: unknown): TraceIntakeQuestion[] {
  if (!Array.isArray(raw)) return []
  const out: TraceIntakeQuestion[] = []
  for (const item of raw.slice(0, 3)) {
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const id = typeof row.id === 'string' ? row.id.trim() : ''
    const prompt = typeof row.prompt === 'string' ? row.prompt.trim() : ''
    if (!id || !prompt) continue
    const options = Array.isArray(row.options)
      ? row.options
          .map((opt) => {
            if (!opt || typeof opt !== 'object') return null
            const o = opt as Record<string, unknown>
            const oid = typeof o.id === 'string' ? o.id.trim() : ''
            const label = typeof o.label === 'string' ? o.label.trim() : ''
            return oid && label ? { id: oid, label } : null
          })
          .filter((opt): opt is TraceIntakeOption => Boolean(opt))
      : undefined
    out.push({ id, prompt, options: options?.length ? options : undefined })
  }
  return out
}

export function formatIntakeAskForTrace(questions: TraceIntakeQuestion[]): string {
  if (!questions.length) return ''
  if (questions.length === 1) return questions[0]!.prompt
  return questions.map((q, i) => `${i + 1}. ${q.prompt}`).join('\n')
}

export function formatIntakeAnswerForTrace(
  questions: TraceIntakeQuestion[],
  answers: Record<string, string | string[]>
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
  const free = typeof answers._freeText === 'string' ? answers._freeText.trim() : ''
  if (free && !lines.some((line) => line.includes(free))) lines.push(free)
  return lines.join('\n') || free || '已确认'
}
