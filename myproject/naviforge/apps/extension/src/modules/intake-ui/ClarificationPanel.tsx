import { useMemo, useState } from 'react'

import type { ClarificationQuestion } from '@naviforge/intake'

import { buildIntakeAnswerPayload, type IntakeSession } from './session.js'

export function ClarificationPanel({
  session,
  onSubmit,
  disabled,
}: {
  session: IntakeSession
  onSubmit: (json: string) => void | Promise<void>
  disabled?: boolean
}) {
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
    <div className="mx-3 mb-2 space-y-3 rounded-xl border border-blue-200 bg-blue-50/80 p-3 text-sm">
      <p className="font-medium text-blue-950">澄清需求（第 {session.round + 1} 轮）</p>
      {questions.map((question: ClarificationQuestion) => (
        <fieldset key={question.id} className="space-y-1.5">
          <legend className="text-blue-900">{question.prompt}</legend>
          {question.kind === 'text' || !question.options?.length ? (
            <input
              className="w-full rounded-md border border-blue-200 bg-white px-2 py-1 text-sm"
              disabled={disabled}
              onChange={(e) => setSingle(question.id, e.target.value)}
            />
          ) : question.kind === 'single' ? (
            <div className="space-y-1">
              {question.options.map((opt) => (
                <label key={opt.id} className="flex cursor-pointer items-start gap-2 rounded-md px-1 py-0.5 hover:bg-blue-100/80">
                  <input
                    type="radio"
                    name={question.id}
                    disabled={disabled}
                    onChange={() => setSingle(question.id, opt.id)}
                  />
                  <span>
                    <span className="text-blue-950">{opt.label}</span>
                    {opt.description ? (
                      <span className="block text-xs text-blue-800/80">{opt.description}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <div className="space-y-1">
              {question.options.map((opt) => (
                <label key={opt.id} className="flex cursor-pointer items-start gap-2 rounded-md px-1 py-0.5 hover:bg-blue-100/80">
                  <input
                    type="checkbox"
                    disabled={disabled}
                    onChange={() => toggleMulti(question.id, opt.id)}
                  />
                  <span className="text-blue-950">{opt.label}</span>
                </label>
              ))}
            </div>
          )}
        </fieldset>
      ))}
      <label className="block text-xs text-blue-900">
        补充说明（可选）
        <input
          className="mt-1 w-full rounded-md border border-blue-200 bg-white px-2 py-1 text-sm"
          disabled={disabled}
          value={freeText}
          onChange={(e) => setFreeText(e.target.value)}
        />
      </label>
      <button
        type="button"
        disabled={disabled}
        className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-40"
        onClick={() => {
          const payload = buildIntakeAnswerPayload(session, {
            ...values,
            ...(freeText.trim() ? { _freeText: freeText.trim() } : {}),
          })
          void onSubmit(payload)
        }}
      >
        确认并继续
      </button>
    </div>
  )
}
