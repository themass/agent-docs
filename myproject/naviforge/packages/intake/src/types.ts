/** Pre-execution clarification protocol (DSH / DeerFlow-style intake). */

export type IntakeMode = 'off' | 'auto' | 'always'

export type ClarificationOption = {
  id: string
  label: string
  description?: string
}

export type ClarificationQuestion = {
  id: string
  prompt: string
  kind: 'single' | 'multi' | 'text'
  options?: ClarificationOption[]
  required?: boolean
  defaultOptionId?: string
}

export type IntakeAnswerMap = Record<string, string | string[]>

export type IntakeQuestionPayload = {
  round: number
  questions: ClarificationQuestion[]
}

export type IntakeAnswerPayload = {
  round: number
  answers: IntakeAnswerMap
  freeText?: string
}

export type IntakeCompletePayload = {
  summary: string
  assumptions: string[]
  roundCount: number
}

export const MAX_INTAKE_ROUNDS = 5
export const MAX_QUESTIONS_PER_ROUND = 3
