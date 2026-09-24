import { ChevronDown, Languages } from 'lucide-react'

import { useI18n } from '../../i18n'
import { cn } from '../../lib/cn'
import {
  SPEECH_RECOGNITION_LANGS,
  speechLangConfigFromSelect,
  speechLangSelectValue,
  type SpeechLangConfig,
} from '../../lib/speech-lang'

export function SpeechLangSelect({
  config,
  onChange,
  variant,
}: {
  config: SpeechLangConfig
  onChange: (next: SpeechLangConfig) => void
  variant: 'orb' | 'bar'
}) {
  const { t } = useI18n()
  const isOrb = variant === 'orb'

  return (
    <label
      className={cn(
        'relative inline-flex max-w-full items-center gap-1.5 rounded-full px-2.5 py-1',
        isOrb
          ? 'bg-white/90 shadow-sm ring-1 ring-sky-200/80 backdrop-blur-md'
          : 'bg-white/80 ring-1 ring-red-200/70'
      )}
    >
      <Languages
        className={cn('size-3.5 shrink-0', isOrb ? 'text-sky-600' : 'text-red-600')}
        aria-hidden
      />
      <span className={cn('shrink-0 text-[10px]', isOrb ? 'text-sky-600/80' : 'text-red-700/75')}>
        {t('chat.voice.speechLangLabel')}
      </span>
      <select
        className={cn(
          'max-w-[9.5rem] cursor-pointer appearance-none truncate bg-transparent pr-4 text-[11px] font-medium outline-none',
          isOrb ? 'text-sky-900' : 'text-red-900'
        )}
        value={speechLangSelectValue(config)}
        aria-label={t('chat.voice.speechLangLabel')}
        onChange={(event) => onChange(speechLangConfigFromSelect(event.target.value, config))}
      >
        <option value="auto">{t('chat.voice.speechLangAuto')}</option>
        {SPEECH_RECOGNITION_LANGS.map((lang) => (
          <option key={lang.id} value={lang.id}>
            {t(lang.labelKey)}
          </option>
        ))}
      </select>
      <ChevronDown
        className={cn(
          'pointer-events-none absolute right-2 size-3 shrink-0 opacity-50',
          isOrb ? 'text-sky-700' : 'text-red-700'
        )}
        aria-hidden
      />
    </label>
  )
}
