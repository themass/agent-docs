import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  BookOpen,
  Brain,
  ChevronDown,
  CircleCheck,
  Eye,
  Info,
  Pencil,
  RotateCcw,
  Sparkles,
  Zap,
} from 'lucide-react'

import {
  formatDurationMs,
  reflectionLines,
  turnActions,
  turnIntent,
  turnTimings,
  type RunTrace,
  type TraceGroup,
} from '../../chat/chat-events'
import type { RecordView } from '../../lib/agent-event-projection'
import { cn } from '../../lib/cn'
import { useI18n, type LocaleId } from '../../i18n'
import { CollapsibleBlock } from './collapsible-text'
import { VoiceCard } from './voice-card'
import { ZoomableImage } from './zoomable-image'
import { WorkspacePathText, WorkspacePathActions, workspacePathFromBody } from './workspace-path-link'

export const consoleCardClass =
  'rounded-2xl border border-black/[0.06] bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05)] select-text'

function formatClock(at: number, locale: LocaleId): string {
  const tag = locale === 'zh-CN' ? 'zh-CN' : locale === 'es' ? 'es' : 'en-US'
  return new Date(at).toLocaleTimeString(tag, {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
  })
}

function compactArgs(event: RecordView): string {
  const raw = event.request ?? event.meta ?? ''
  if (!raw) return ''
  try {
    return JSON.stringify(JSON.parse(raw))
  } catch {
    return raw
  }
}

export function UserBubble({ event }: { event: RecordView }) {
  const { t } = useI18n()
  const slashMatch = event.body?.trim().match(/^(\/(?:skill:[\w.-]+|[\w-]+))(?:\s+([\s\S]*))?$/)
  const slashToken = slashMatch?.[1]
  const slashBody = slashMatch?.[2]?.trim()
  const bodyText = event.body?.trim()
  const hasMedia = Boolean(event.imageDataUrl || event.audioDataUrl || event.audioPath)
  return (
    <div className="flex justify-end">
      <div className="max-w-[min(88%,320px)] overflow-hidden rounded-[20px] bg-neutral-100 text-[13px] leading-relaxed text-neutral-800 shadow-sm">
        {event.imageDataUrl ? (
          <div className="border-b border-neutral-200/70 p-2">
            <ZoomableImage
              src={event.imageDataUrl}
              label={bodyText || event.imageLabel || t('chat.stepCard.imageLabel')}
              className="block overflow-hidden rounded-xl"
              imgClassName="max-h-[120px] max-w-[200px] rounded-xl border border-black/5 object-cover shadow-sm"
            />
          </div>
        ) : null}
        {event.audioDataUrl || event.audioPath ? (
          <VoiceCard src={event.audioDataUrl} path={event.audioPath} bubble />
        ) : null}
        {slashToken ? (
          <div className={cn('px-3 py-2', hasMedia && 'border-t border-neutral-200/70')}>
            <code className="inline-flex rounded-md border border-neutral-200 bg-white px-2 py-1 font-mono text-[12px] font-semibold text-red-600 shadow-sm">
              {slashToken}
            </code>
            {slashBody ? (
              <p className="mt-2 whitespace-pre-wrap text-neutral-800">{slashBody}</p>
            ) : null}
          </div>
        ) : null}
        {bodyText && !slashToken ? (
          <div className={cn('px-4 py-2.5', hasMedia && !slashToken && 'border-t border-neutral-200/70')}>
            <CollapsibleBlock text={event.body}>{(visible) => <p className="whitespace-pre-wrap">{visible}</p>}</CollapsibleBlock>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function QuestionBubble({ event }: { event: RecordView }) {
  const { t } = useI18n()
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] overflow-hidden rounded-[20px] border border-blue-200 bg-blue-50 text-[13px] leading-relaxed text-blue-950">
        <div className="border-b border-blue-200/80 px-3 py-1.5 text-xs font-semibold text-blue-800">
          {event.title || t('chat.traceView.question')}
        </div>
        <div className="px-4 py-2.5">
          <CollapsibleBlock text={event.body}>{(visible) => <p className="whitespace-pre-wrap">{visible}</p>}</CollapsibleBlock>
        </div>
      </div>
    </div>
  )
}

export function ThinkingChip({
  detail,
  reasoning,
  feed = [],
}: {
  detail?: string | null
  reasoning?: string | null
  feed?: string[]
}) {
  const { t } = useI18n()
  const [detailsOpen, setDetailsOpen] = useState(true)
  const feedEndRef = useRef<HTMLDivElement>(null)
  const headline = detail?.trim()
  const lines = feed.filter((line) => line && line !== headline)

  useEffect(() => {
    if (!detailsOpen || !lines.length) return
    feedEndRef.current?.scrollIntoView({ block: 'nearest' })
  }, [detailsOpen, lines.length, lines[lines.length - 1]])

  return (
    <div
      data-testid="thinking-chip"
      className={cn(
        consoleCardClass,
        'border-sky-200 bg-white px-3 py-2'
      )}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex shrink-0 items-center gap-1" aria-hidden>
          <span className="size-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.3s]" />
          <span className="size-1.5 rounded-full bg-sky-500 animate-bounce [animation-delay:-0.15s]" />
          <span className="size-1.5 rounded-full bg-sky-500 animate-bounce" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-start gap-1.5">
            <p className="min-w-0 flex-1 text-[11px] font-medium leading-snug text-sky-800">
              <span className="text-sky-700">{t('chat.stepCard.thinking')}</span>
              {headline ? (
                <>
                  <span className="font-normal text-sky-500/90"> · </span>
                  <span className="font-normal">{headline}</span>
                </>
              ) : null}
            </p>
            {lines.length || reasoning ? (
              <button
                type="button"
                className="inline-flex shrink-0 items-center gap-0.5 rounded px-1 py-0.5 text-[10px] text-sky-600/80 hover:bg-sky-50 hover:text-sky-800"
                aria-expanded={detailsOpen}
                aria-label={
                  detailsOpen
                    ? t('chat.stepCard.collapseActivity')
                    : t('chat.stepCard.expandActivity', { count: String(lines.length) })
                }
                onClick={() => setDetailsOpen((open) => !open)}
              >
                <ChevronDown
                  className={cn('size-3 transition-transform', !detailsOpen && '-rotate-90')}
                />
              </button>
            ) : null}
          </div>
          {detailsOpen && reasoning ? (
            <p className="mt-1 text-[10px] leading-relaxed text-sky-700/80">{reasoning}</p>
          ) : null}
          {detailsOpen && lines.length ? (
            <div
              className="mt-1.5 max-h-28 overflow-y-auto overscroll-contain [scrollbar-gutter:stable] border-t border-sky-100 pt-1.5 pr-2"
              aria-label={t('chat.stepCard.liveFeed')}
            >
              <ul className="space-y-0.5">
                {lines.map((line, index) => (
                  <li key={`${index}-${line}`} className="break-words text-[10px] leading-snug text-sky-800/75">
                    {line}
                  </li>
                ))}
              </ul>
              <div ref={feedEndRef} className="h-px shrink-0" aria-hidden />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function NavChip({ url }: { url: string }) {
  const { t } = useI18n()
  return (
    <div className={cn(consoleCardClass, 'flex items-center gap-2.5 px-3.5 py-2.5 text-[13px]')}>
      <Eye className="size-4 shrink-0 text-emerald-600" />
      <p className="min-w-0 truncate text-neutral-600">
        {t('chat.stepCard.navPrefix')} <span className="text-neutral-400">→</span>{' '}
        <span className="text-neutral-800">{url}</span>
      </p>
    </div>
  )
}

export function DoneBar({ ok, tool }: { ok: boolean; tool?: string }) {
  const { t } = useI18n()
  const label = ok
    ? tool
      ? t('chat.stepCard.doneTool', { tool })
      : t('chat.stepCard.done')
    : t('chat.stepCard.failedTool', { tool: tool ?? '' })
  return (
    <div
      className={cn(
        consoleCardClass,
        'flex items-center gap-2 px-3.5 py-2 text-[13px] font-medium',
        ok ? 'bg-emerald-50/90 text-emerald-800' : 'bg-red-50 text-red-800'
      )}
    >
      <CircleCheck className={cn('size-4 shrink-0', ok ? 'text-emerald-600' : 'text-red-500')} />
      {label}
    </div>
  )
}

function inlineMarkdown(text: string): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\[[^\]]+\]\(https?:[^)]+\))/g)
  return parts.map((part, index) => {
    const bold = /^\*\*([^*]+)\*\*$/.exec(part)
    if (bold) return <strong key={index}>{bold[1]}</strong>
    const link = /^\[([^\]]+)\]\((https?:[^)]+)\)$/.exec(part)
    if (link) {
      return (
        <a
          key={index}
          href={link[2]}
          target="_blank"
          rel="noreferrer"
          className="text-sky-700 underline decoration-sky-200 underline-offset-2"
        >
          {link[1]}
        </a>
      )
    }
    return part
  })
}

function AnswerBody({ text }: { text: string }) {
  return (
    <div className="space-y-1.5 text-[14px] leading-relaxed text-neutral-800">
      {text.split('\n').map((line, index) => {
        if (!line.trim()) return <div key={index} className="h-1.5" />
        if (line.startsWith('### ')) {
          return (
            <h3 key={index} className="pt-2 text-[15px] font-semibold text-neutral-900">
              {inlineMarkdown(line.slice(4))}
            </h3>
          )
        }
        if (line.startsWith('## ') || line.startsWith('# ')) {
          const body = line.replace(/^#+\s/, '')
          return (
            <h3 key={index} className="pt-2 text-[15px] font-semibold text-neutral-900">
              {inlineMarkdown(body)}
            </h3>
          )
        }
        if (/^[-*]\s/.test(line)) {
          return (
            <div key={index} className="flex gap-2">
              <span className="mt-0.5 text-neutral-400">•</span>
              <span>{inlineMarkdown(line.replace(/^[-*]\s/, ''))}</span>
            </div>
          )
        }
        return <p key={index}>{inlineMarkdown(line)}</p>
      })}
    </div>
  )
}

export function ResultCard({ event, trace }: { event: RecordView; trace?: RunTrace }) {
  const { t } = useI18n()
  const skills = trace?.skills ?? []
  return (
    <article className="rounded-2xl border border-emerald-200 bg-white px-4 py-3.5 shadow-[0_1px_2px_rgba(15,23,42,0.05)]">
      <header className="mb-2.5 flex items-center gap-2 text-emerald-900">
        <CircleCheck className="size-5 shrink-0 text-emerald-700" />
        <span className="text-[16px] font-bold tracking-tight">{t('chat.stepCard.resultTitle')}</span>
      </header>
      <CollapsibleBlock text={event.body}>
        {(visible) => <AnswerBody text={visible} />}
      </CollapsibleBlock>
      <WorkspacePathActions text={event.body} />
      <IoTabs request={event.request} response={event.response} />
      {skills.length ? (
        <p className="mt-3 flex gap-2 border-t border-emerald-100 pt-3 text-[12px] leading-relaxed text-neutral-600">
          <BookOpen className="mt-0.5 size-3.5 shrink-0 text-violet-600" />
          <span>{t('chat.stepCard.skillLine', { skills: skills.join(' · ') })}</span>
        </p>
      ) : null}
    </article>
  )
}

const TONE_ICON = {
  done: Sparkles,
  plan: Pencil,
  note: Info,
} as const

const TONE_CLASS = {
  done: 'text-sky-500',
  plan: 'text-neutral-500',
  note: 'text-sky-600',
} as const

export function StepCard({
  stepNo,
  group,
  detailed,
  prevAt,
  onRequeue,
}: {
  stepNo: number
  group: TraceGroup<RecordView>
  detailed: boolean
  prevAt?: number
  onRequeue?: (intent: string) => void
}) {
  const { t, locale } = useI18n()
  const items = group.items
  const timings = turnTimings(items, prevAt)
  const reflections = reflectionLines(items)
  const actions = turnActions(items)
  const intent = onRequeue ? turnIntent(group) : null
  const modelIo = items.find((event) => event.variant === 'step' && (event.request || event.response))

  return (
    <article className={cn(consoleCardClass, 'px-3 py-2.5 text-[12px]')}>
      <header className="flex items-center gap-2 text-neutral-500">
        <h3 className="text-[16px] font-bold tracking-tight text-neutral-900">
          {t('chat.stepCard.stepTitle', { n: stepNo })}
        </h3>
        {intent ? (
          <button
            type="button"
            onClick={() => onRequeue?.(intent)}
            className="rounded p-0.5 hover:bg-neutral-100 hover:text-neutral-800"
            title={t('chat.stepCard.rerunIntentTitle')}
            aria-label={t('chat.stepCard.rerunIntentAria')}
          >
            <RotateCcw className="size-3" />
          </button>
        ) : null}
        <span className="ml-auto flex items-center gap-2.5 text-[11px] tabular-nums">
          <span>{formatClock(timings.startedAt, locale)}</span>
          {timings.thinkMs > 0 ? (
            <span className="inline-flex items-center gap-0.5">
              <Brain className="size-3" />
              {formatDurationMs(timings.thinkMs)}
            </span>
          ) : null}
          {timings.actMs > 0 ? (
            <span className="inline-flex items-center gap-0.5">
              <Zap className="size-3" />
              {formatDurationMs(timings.actMs)}
            </span>
          ) : null}
        </span>
      </header>

      {reflections.length ? (
        <ul className="mt-2 space-y-1">
          {reflections.map((line, index) => {
            const Icon = TONE_ICON[line.tone]
            return (
              <li key={`${line.tone}-${index}`} className="flex gap-2 leading-relaxed text-neutral-700">
                <Icon className={cn('mt-0.5 size-3.5 shrink-0', TONE_CLASS[line.tone])} />
                <span className={detailed ? 'whitespace-pre-wrap' : 'line-clamp-3'}>{line.text}</span>
              </li>
            )
          })}
        </ul>
      ) : null}

      {actions.length ? (
        <section className="mt-2">
          <h4 className="text-[10px] font-semibold uppercase tracking-wide text-neutral-400">
            {t('chat.stepCard.actions')}
          </h4>
          <ul className="mt-1 space-y-1.5">
            {actions.map((event) => {
              const args = compactArgs(event)
              const savedPath = event.body ? workspacePathFromBody(event.body) : null
              return (
              <li key={event.id}>
                <p className="flex gap-1.5 font-medium text-neutral-800">
                  <Zap className="mt-0.5 size-3 shrink-0 text-sky-500" />
                  <span className="min-w-0 break-all">
                    {event.title}
                    {args ? (
                      <span className="font-normal text-neutral-500">
                        {' '}
                        {detailed ? args : args.slice(0, 180)}
                      </span>
                    ) : null}
                  </span>
                </p>
                {event.body ? (
                  <div className="mt-0.5 ml-5 flex gap-1.5 text-neutral-600">
                    <CircleCheck
                      className={cn(
                        'mt-0.5 size-3 shrink-0',
                        event.variant === 'error' ? 'text-red-500' : 'text-emerald-600'
                      )}
                    />
                    {savedPath ? (
                      <WorkspacePathText text={event.body} />
                    ) : (
                      <span className={detailed ? 'whitespace-pre-wrap break-words' : 'line-clamp-2'}>
                        {event.body}
                      </span>
                    )}
                  </div>
                ) : null}
              </li>
              )
            })}
          </ul>
        </section>
      ) : null}

      {modelIo ? <IoTabs request={modelIo.request} response={modelIo.response} /> : null}
    </article>
  )
}

function IoTabs({
  request,
  response,
}: {
  request?: string
  response?: string
}) {
  const { t } = useI18n()
  const [tab, setTab] = useState<'request' | 'response' | null>(null)
  if (!request && !response) return null
  const empty = t('chat.stepCard.emptyDash')

  return (
    <div className="mt-3 border-t border-black/[0.04] pt-2">
      <div className="flex gap-4 text-[12px] text-neutral-400">
        <button
          type="button"
          className={cn('hover:text-neutral-700', tab === 'request' && 'font-medium text-neutral-800')}
          onClick={() => setTab((cur) => (cur === 'request' ? null : 'request'))}
        >
          {t('chat.stepCard.sentToModel')}
        </button>
        <button
          type="button"
          className={cn('hover:text-neutral-700', tab === 'response' && 'font-medium text-neutral-800')}
          onClick={() => setTab((cur) => (cur === 'response' ? null : 'response'))}
        >
          {t('chat.stepCard.modelReply')}
        </button>
      </div>
      {tab ? (
        <pre className="mt-2 max-h-[28rem] overflow-auto whitespace-pre-wrap break-all rounded-xl bg-neutral-50 px-2.5 py-2 text-[11px] leading-relaxed text-neutral-600">
          {tab === 'request' ? request || empty : response || empty}
        </pre>
      ) : null}
    </div>
  )
}
