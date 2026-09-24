import { Mic, Square } from 'lucide-react'

import { useI18n } from '../../i18n'
import { cn } from '../../lib/cn'
import type { SpeechLangConfig } from '../../lib/speech-lang'
import { SpeechLangSelect } from './speech-lang-select'

export function VoiceCaptureBar({
  interim,
  transcript,
  speechLangConfig,
  onSpeechLangChange,
  onCancel,
  onFinish,
}: {
  interim: string
  transcript: string
  speechLangConfig: SpeechLangConfig
  onSpeechLangChange: (next: SpeechLangConfig) => void
  onCancel: () => void
  onFinish: () => void
}) {
  const { t } = useI18n()
  const live = [transcript.trim(), interim.trim()].filter(Boolean).join('')
  const bars = [0.35, 0.65, 0.45, 0.85, 0.5, 0.75, 0.4, 0.6]

  return (
    <div
      className="mb-2 overflow-hidden rounded-2xl border border-red-200/80 bg-red-50/90 px-3 py-2.5 shadow-[0_4px_20px_rgba(239,68,68,0.08)]"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <span className="relative flex size-2.5 shrink-0">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-60" />
          <span className="relative inline-flex size-2.5 rounded-full bg-red-500" />
        </span>
        <Mic className="size-3.5 shrink-0 text-red-600" />
        <p className="min-w-0 flex-1 text-[12px] font-medium text-red-800">{t('chat.voice.listeningTitle')}</p>
        <div className="flex h-4 items-end gap-0.5" aria-hidden>
          {bars.map((height, index) => (
            <span
              key={index}
              className="w-0.5 animate-pulse rounded-full bg-red-400/90"
              style={{
                height: `${Math.round(height * 100)}%`,
                animationDelay: `${index * 90}ms`,
              }}
            />
          ))}
        </div>
      </div>

      <div className="mt-2 flex justify-start">
        <SpeechLangSelect
          config={speechLangConfig}
          onChange={onSpeechLangChange}
          variant="bar"
        />
      </div>

      <p className="mt-2 min-h-[1.25rem] text-[13px] leading-relaxed text-neutral-800">
        {live ? (
          <>
            {transcript.trim() ? <span>{transcript.trim()}</span> : null}
            {interim.trim() ? (
              <span className={cn(transcript.trim() ? 'text-neutral-500' : 'text-neutral-800')}>
                {transcript.trim() ? '' : ''}
                {interim.trim()}
              </span>
            ) : null}
            {interim.trim() ? (
              <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-red-500 align-middle" />
            ) : null}
          </>
        ) : (
          <span className="text-neutral-500">{t('chat.voice.listeningHint')}</span>
        )}
      </p>

      <p className="mt-1 text-[10px] text-red-700/80">{t('chat.voice.listeningFootnote')}</p>

      <div className="mt-2 flex items-center justify-end gap-2">
        <button
          type="button"
          className="rounded-full px-3 py-1 text-[12px] text-neutral-600 hover:bg-white/70"
          onClick={onCancel}
        >
          {t('chat.voice.cancel')}
        </button>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-full bg-red-600 px-3 py-1 text-[12px] font-medium text-white hover:bg-red-700"
          onClick={onFinish}
        >
          <Square className="size-2.5 fill-current" />
          {t('chat.voice.finish')}
        </button>
      </div>
    </div>
  )
}
