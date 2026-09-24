import type { RecordView } from '../../lib/agent-event-projection'
import { isContextView } from '../../lib/agent-event-projection'
import { cn } from '../../lib/cn'
import { useI18n } from '../../i18n'
import { CollapsibleBlock, CollapsibleText } from './collapsible-text'
import { WorkspacePathActions } from './workspace-path-link'

const variantStyles: Record<string, string> = {
  user: 'border-primary/25 bg-primary/5',
  task: 'border-border bg-card',
  control: 'border-amber-300 bg-amber-50',
  step: 'border-sky-200 bg-sky-50/80',
  tool: 'border-violet-200 bg-violet-50/80',
  network: 'border-amber-200 bg-amber-50/80',
  recovery: 'border-orange-200 bg-orange-50/70',
  result: 'border-emerald-200 bg-emerald-50/80',
  success: 'border-green-200 bg-green-50',
  error: 'border-red-200 bg-red-50',
  warning: 'border-amber-200 bg-amber-50',
  question: 'border-blue-200 bg-blue-50',
  system: 'border-transparent bg-transparent text-muted-foreground',
}

const badgeStyles: Record<string, string> = {
  user: 'bg-primary text-primary-foreground',
  task: 'bg-muted text-foreground',
  control: 'bg-amber-600 text-white',
  step: 'bg-sky-600 text-white',
  tool: 'bg-violet-600 text-white',
  network: 'bg-amber-600 text-white',
  recovery: 'bg-orange-600 text-white',
  result: 'bg-emerald-600 text-white',
  success: 'bg-green-600 text-white',
  error: 'bg-red-600 text-white',
  warning: 'bg-amber-500 text-white',
  question: 'bg-blue-600 text-white',
  system: 'bg-neutral-800 text-white',
}

export function MessageCard({ event }: { event: RecordView }) {
  const { t } = useI18n()
  const context = isContextView(event)
  const compact = event.variant === 'system' && !context
  const multiLine = event.body.includes('\n') && !context

  return (
    <article
      className={cn(
        'rounded-2xl border px-3 py-2.5 select-text',
        compact ? 'px-1 py-1 text-sm' : 'text-[13px]',
        variantStyles[event.variant]
      )}
    >
      <div className="flex items-start gap-2.5 min-w-0">
        <span
          className={cn(
            'shrink-0 rounded-md px-2 py-0.5 text-[13px] font-bold leading-5 tracking-tight',
            badgeStyles[event.variant]
          )}
        >
          {event.title}
          {event.repeat && event.repeat > 1 ? ` ×${event.repeat}` : ''}
        </span>
        <div className="min-w-0 flex-1 space-y-1">
          {event.meta ? <p className="text-sm text-muted-foreground">{event.meta}</p> : null}
          {context ? (
            <CollapsibleText text={event.body} pre />
          ) : multiLine ? (
            <CollapsibleBlock text={event.body}>
              {(visible) => (
                <ul className="space-y-1 text-sm leading-relaxed">
                  {visible.split('\n').map((line, index) => (
                    <li key={`${index}:${line.slice(0, 24)}`} className="break-words">
                      {line}
                    </li>
                  ))}
                </ul>
              )}
            </CollapsibleBlock>
          ) : (
            <CollapsibleText text={event.body} />
          )}
          <WorkspacePathActions text={event.body} />
          {event.repeat && event.repeat > 1 ? (
            <p className="text-xs text-muted-foreground">
              {t('chat.stepCard.repeatFold', { count: event.repeat })}
            </p>
          ) : null}
        </div>
      </div>
    </article>
  )
}
