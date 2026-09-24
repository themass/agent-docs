import { loadResolvedLocale } from '../../i18n/I18nProvider'
import { setActiveLocale, t } from '../../i18n/t'

export type RecordingHudCopy = {
  title: string
  start: string
  stop: string
  recording: string
  saving: string
  saved: string
  savedEmpty: string
  whereReplay: string
  viewReplay: string
  recordAgain: string
  hint: string
  close: string
  error: string
  errorHint: string
  recordingPage: string
  dragHint: string
}

export async function loadRecordingHudCopy(): Promise<RecordingHudCopy> {
  const locale = await loadResolvedLocale()
  setActiveLocale(locale)
  return {
    title: t('recordingHud.title'),
    start: t('recordingHud.start'),
    stop: t('recordingHud.stop'),
    recording: t('recordingHud.recording'),
    saving: t('recordingHud.saving'),
    saved: t('recordingHud.saved'),
    savedEmpty: t('recordingHud.savedEmpty'),
    whereReplay: t('recordingHud.whereReplay'),
    viewReplay: t('recordingHud.viewReplay'),
    recordAgain: t('recordingHud.recordAgain'),
    hint: t('recordingHud.hint'),
    close: t('recordingHud.close'),
    error: t('recordingHud.error'),
    errorHint: t('recordingHud.errorHint'),
    recordingPage: t('recordingHud.recordingPage'),
    dragHint: t('recordingHud.dragHint'),
  }
}
