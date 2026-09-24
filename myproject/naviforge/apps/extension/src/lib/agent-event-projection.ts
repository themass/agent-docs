import type { TraceRecord, TraceView } from '@naviforge/session'
import { projectTraceView, projectTraceViews } from '@naviforge/session'

import { formatListBody, type ListResultItem } from './list-result-format'
import { DEFAULT_LOCALE, type LocaleId } from '../i18n/locales'
import { getActiveLocale, t } from '../i18n/t'

/** Canonical title from `@naviforge/session` trace projection (never localized at source). */
export const TRACE_CONTEXT_CANONICAL = 'Context'

/** Render-only data. It is never persisted or sent back to the model. */
export type RecordView = TraceView & { contextPinned?: boolean }

function localizeView(view: TraceView, locale: LocaleId = getActiveLocale()): RecordView {
  const isContext = view.variant === 'system' && view.title === TRACE_CONTEXT_CANONICAL
  const title =
    view.variant === 'task'
      ? t('chat.traceView.task', undefined, locale)
      : view.variant === 'user'
        ? t('chat.traceView.you', undefined, locale)
        : view.variant === 'result'
          ? t('chat.traceView.result', undefined, locale)
          : view.variant === 'question'
            ? t('chat.traceView.question', undefined, locale)
            : view.variant === 'error' && view.title === 'Blocked'
              ? t('chat.traceView.blocked', undefined, locale)
              : view.variant === 'error'
                ? t('chat.traceView.failed', undefined, locale)
                : isContext
                  ? t('chat.stepCard.contextTitle', undefined, locale)
                  : view.variant === 'tools'
                    ? t('chat.traceView.tools', undefined, locale)
                    : view.title
  return { ...view, title, contextPinned: isContext ? true : undefined }
}

export function isContextView(event: RecordView): boolean {
  return event.contextPinned === true
}

export function recordView(record: TraceRecord, locale?: LocaleId): RecordView | null {
  const view = projectTraceView(record)
  return view ? localizeView(view, locale ?? getActiveLocale()) : null
}

export function recordViews(records: readonly TraceRecord[], locale?: LocaleId): RecordView[] {
  const loc = locale ?? getActiveLocale()
  return projectTraceViews(records).map((view) => localizeView(view, loc))
}

export { formatListBody, type ListResultItem }
