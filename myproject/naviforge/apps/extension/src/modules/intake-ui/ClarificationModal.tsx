import { X } from 'lucide-react'
import { useMemo, useState } from 'react'

import type { ClarificationQuestion } from '@naviforge/intake'

import { useI18n } from '../../i18n'
import { textInputLangProps } from '../../lib/text-input-lang'
import { buildIntakeAnswerPayload, type IntakeSession } from './session.js'

function ClarificationForm({
  session,
  onSubmit,
  disabled,
  submitLabel,
}: {
  session: IntakeSession
  onSubmit: (json: string) => void | Promise<void>
  disabled?: boolean
  submitLabel: string
}) {
  const { t } = useI18n()
  const inputLang = textInputLangProps()
  const [values, setValues] = useState<Record<string, string | string[]>>({})
  const [freeText, setFreeText] = useState('')

  const questions = useMemo(() => session.questions, [session])

  function setSingle(id: string, value: string) {
    setValues((prev) => ({ ...prev, [id]: value }))
  }

  function toggleMulti(id: string, optionId: string) {
    setValues((prev) => {
      const current = prev[id]
      const list = Array.isArray(current) ? [...current] : current ? [String(current)] : []
      const next = list.includes(optionId) ? list.filter((v) => v !== optionId) : [...list, optionId]
      return { ...prev, [id]: next }
    })
  }

  return (
    <div className="space-y-4">
      {questions.map((question: ClarificationQuestion) => (
        <fieldset key={question.id} className="space-y-2">
          <legend className="text-sm font-medium text-foreground">{question.prompt}</legend>
          {question.kind === 'text' || !question.options?.length ? (
            <input
              className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary/30 focus:ring-2"
              disabled={disabled}
              autoCapitalize={inputLang.autoCapitalize}
              autoCorrect={inputLang.autoCorrect}
              spellCheck={inputLang.spellCheck}
              style={inputLang.style}
              onChange={(e) => setSingle(question.id, e.target.value)}
            />
          ) : question.kind === 'single' ? (
            <div className="space-y-1">
              {question.options.map((opt) => (
                <label
                  key={opt.id}
                  className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-transparent px-2 py-2 hover:border-border hover:bg-muted/40"
                >
                  <input
                    type="radio"
                    name={question.id}
                    className="mt-0.5"
                    disabled={disabled}
                    onChange={() => setSingle(question.id, opt.id)}
                  />
                  <span className="min-w-0">
                    <span className="text-sm text-foreground">{opt.label}</span>
                    {opt.description ? (
                      <span className="mt-0.5 block text-xs text-muted-foreground">{opt.description}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {question.options.map((opt) => (
                <label
                  key={opt.id}
                  className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-transparent px-2 py-2 hover:border-border hover:bg-muted/40"
                >
                  <input
                    type="checkbox"
                    className="mt-0.5"
                    disabled={disabled}
                    onChange={() => toggleMulti(question.id, opt.id)}
                  />
                  <span className="text-sm text-foreground">{opt.label}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      ))}
      <label className="block text-xs text-muted-foreground">
        {t('chat.clarify.freeText')}
        <textarea
          className="mt-1.5 w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary/30 focus:ring-2"
          rows={2}
          disabled={disabled}
          value={freeText}
          autoCapitalize={inputLang.autoCapitalize}
          autoCorrect={inputLang.autoCorrect}
          spellCheck={inputLang.spellCheck}
          style={inputLang.style}
          onChange={(e) => setFreeText(e.target.value)}
        />
      </label>
      <button
        type="button"
        disabled={disabled}
        className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
        onClick={() => {
          const payload = buildIntakeAnswerPayload(session, {
            ...values,
            ...(freeText.trim() ? { _freeText: freeText.trim() } : {}),
          })
          void onSubmit(payload)
        }}
      >
        {submitLabel}
      </button>
    </div>
  )
}

export function ClarificationModal({
  session,
  onSubmit,
  onStop,
  disabled,
}: {
  session: IntakeSession
  onSubmit: (json: string) => void | Promise<void>
  onStop?: () => void
  disabled?: boolean
}) {
  const { t } = useI18n()

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-3 backdrop-blur-[2px] sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="clarify-title"
    >
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3">
          <div>
            <p id="clarify-title" className="text-base font-semibold text-foreground">
              {t('chat.clarify.title')}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t('chat.clarify.round', { n: String(session.round + 1) })}
            </p>
          </div>
          {onStop ? (
            <button
              type="button"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
              aria-label={t('chat.clarify.stop')}
              onClick={onStop}
            >
              <X className="size-4" />
            </button>
          ) : null}
        </div>
        <div className="max-h-[min(70vh,32rem)] overflow-y-auto px-4 py-4">
          <ClarificationForm
            session={session}
            disabled={disabled}
            submitLabel={t('chat.clarify.confirm')}
            onSubmit={onSubmit}
          />
        </div>
      </div>
    </div>
  )
}
