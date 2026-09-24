import type { ClarificationQuestion } from '@naviforge/intake'
import type { TraceRecord } from '@naviforge/session'

export type IntakeSession = {
  round: number
  questions: ClarificationQuestion[]
}

/** Open intake round for the latest run: question not yet answered on the same runId. */
export function latestIntakeSession(records: readonly TraceRecord[]): IntakeSession | null {
  let questionIndex = -1
  let question: IntakeSession | null = null
  let questionRunId: string | undefined

  for (let i = records.length - 1; i >= 0; i--) {
    const record = records[i]
    if (!record || record.type !== 'intake.question') continue
    const payload = record.payload as { round?: number; questions?: ClarificationQuestion[] }
    if (!Array.isArray(payload.questions) || !payload.questions.length) return null
    question = { round: payload.round ?? 0, questions: payload.questions as ClarificationQuestion[] }
    questionRunId = record.runId
    questionIndex = i
    break
  }

  if (!question || questionRunId === undefined || questionIndex < 0) return null

  for (let i = questionIndex + 1; i < records.length; i++) {
    const record = records[i]
    if (!record || record.runId !== questionRunId) continue
    if (record.type === 'intake.complete') return null
    if (record.type === 'intake.answer') {
      const round = (record.payload as { round?: number }).round ?? 0
      if (round >= question.round) return null
    }
  }

  return question
}

export function buildIntakeAnswerPayload(
  session: IntakeSession,
  values: Record<string, string | string[]>
): string {
  return JSON.stringify({ round: session.round, ...values })
}
