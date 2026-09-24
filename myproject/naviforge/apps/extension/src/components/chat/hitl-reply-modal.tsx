import { X } from 'lucide-react'
import { useState } from 'react'

import { textInputLangProps } from '../../lib/text-input-lang'
import { useI18n } from '../../i18n'

export function HitlReplyModal({
  question,
  onSubmit,
  onStop,
  disabled,
}: {
  question: string
  onSubmit: (text: string) => void | Promise<void>
  onStop?: () => void
  disabled?: boolean
}) {
  const { t } = useI18n()
  const inputLang = textInputLangProps()
  const [answer, setAnswer] = useState('')

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/45 p-3 backdrop-blur-[2px] sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-labelledby="hitl-title"
    >
      <div className="relative w-full max-w-md rounded-2xl border border-border bg-background shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border/60 px-4 py-3">
          <div className="min-w-0">
            <p id="hitl-title" className="text-base font-semibold text-foreground">
              {t('chat.hitl.title')}
            </p>
            <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{question}</p>
          </div>
          {onStop ? (
            <button
              type="button"
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted"
              aria-label={t('chat.hitl.stop')}
              onClick={onStop}
            >
              <X className="size-4" />
            </button>
          ) : null}
        </div>
        <div className="space-y-3 px-4 py-4">
          <textarea
            className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary/30 focus:ring-2"
            rows={4}
            disabled={disabled}
            placeholder={t('chat.placeholderReply')}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            autoCapitalize={inputLang.autoCapitalize}
            autoCorrect={inputLang.autoCorrect}
            spellCheck={inputLang.spellCheck}
            style={inputLang.style}
            autoFocus
          />
          <button
            type="button"
            disabled={disabled || !answer.trim()}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            onClick={() => void onSubmit(answer.trim())}
          >
            {t('chat.hitl.confirm')}
          </button>
        </div>
      </div>
    </div>
  )
}
