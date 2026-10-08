import { useEffect, useMemo, useRef, useState, Fragment } from 'react'
import { Sparkles } from 'lucide-react'

import {
  collectRunTrace,
  collapseChatEvents,
  groupByTurn,
  isAgentStepGroup,
  isIdleDoneTurn,
  navigatedUrl,
  partitionChildTraceViews,
  turnAnswer,
  turnProcessItems,
  type RunTrace,
} from '../../chat/chat-events'
import type { RecordView } from '../../lib/agent-event-projection'
import { isContextView } from '../../lib/agent-event-projection'
import { formatListItem } from '../../lib/list-result-format'
import { useI18n } from '../../i18n'
import { MessageCard } from './message-card'
import { CollapsibleText } from './collapsible-text'
import {
  DoneBar,
  NavChip,
  QuestionBubble,
  ResultCard,
  StepCard,
  ThinkingChip,
  UserBubble,
} from './step-card'
import { openOptionsPage } from '../../lib/surface-launch'
import type { WorkspaceRunOutcome } from '../../chat/run-outcome'
import { ToolCatalogPanel } from './tool-catalog-panel'
import { AdBanner } from '../ad-banner'

type TopVideo = { label: string; index: number; title: string; url?: string }

const OUTCOME_STYLES: Record<WorkspaceRunOutcome['kind'], string> = {
  success: 'border-green-200 bg-green-50 text-green-900',
  failed: 'border-red-200 bg-red-50 text-red-900',
  blocked: 'border-amber-200 bg-amber-50 text-amber-900',
  cancelled: 'border-slate-200 bg-slate-50 text-slate-800',
  waiting: 'border-blue-200 bg-blue-50 text-blue-900',
}

export function MessageList({
  events,
  running,
  task,
  topVideos,
  resultsMarked,
  resultsStale,
  listWarnings,
  runOutcome,
  wide,
  onFocusVideo,
  onRequeue,
  showThinking,
  thinkingDetail,
  thinkingReasoning,
  liveFeed,
}: {
  events: RecordView[]
  running: boolean
  task: string
  status?: string
  /** Live detail from runtime (tool name / skill id / model wait). */
  statusDetail?: string | null
  runStartedAt?: number | null
  topVideos?: TopVideo[]
  resultsMarked?: boolean
  resultsStale?: boolean
  listWarnings?: { missed?: string[]; offscreen?: string[]; shortfall?: string }
  runOutcome?: WorkspaceRunOutcome | null
  wide?: boolean
  onFocusVideo?: (video: TopVideo) => void
  /** Queue a turn's goal as a new task. Omit to hide the per-turn re-run affordance. */
  onRequeue?: (intent: string) => void
  showThinking?: boolean
  thinkingDetail?: string | null
  thinkingReasoning?: string | null
  liveFeed?: string[]
}) {
  const { t, locale } = useI18n()
  const bottomRef = useRef<HTMLDivElement>(null)
  const displayEvents = useMemo(() => collapseChatEvents(events), [events])
  const { main: mainEvents, childrenByParent } = useMemo(
    () => partitionChildTraceViews(displayEvents),
    [displayEvents]
  )
  const turns = useMemo(() => groupByTurn(mainEvents), [mainEvents])
  const runTrace = useMemo(() => collectRunTrace(mainEvents), [mainEvents])
  const [detailed, setDetailed] = useState(false)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [displayEvents.length, running, topVideos?.length, runOutcome?.message, liveFeed?.length, showThinking])

  if (!displayEvents.length && !running && !topVideos?.length && !runOutcome) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center text-muted-foreground">
        <Sparkles className="size-8 opacity-40" />
        <p className="text-base font-medium text-foreground">{t('chat.emptyTitle')}</p>
        <p className="text-base leading-relaxed">{t('chat.emptyHint')}</p>
        {task ? <p className="text-sm opacity-60">{t('chat.emptyDraft', { text: task.slice(0, 80) })}</p> : null}
        <AdBanner surface="agentFeed" size="compact" className="mt-4 w-full max-w-md" />
      </div>
    )
  }

  let stepNo = 0
  let prevAt: number | undefined
  let seenAnswer = false

  return (
    <div className="flex flex-1 flex-col min-h-0">
      <div className={`flex-1 overflow-y-auto overflow-x-hidden py-2 min-h-0 select-text ${wide ? 'px-6' : 'px-3'}`} data-chat-selectable>
        <div className="mb-2 flex justify-end">
          <button
            type="button"
            onClick={() => setDetailed((value) => !value)}
            className="rounded-xl border border-black/[0.06] bg-neutral-100 px-3 py-1 text-[13px] text-neutral-600 shadow-sm hover:bg-neutral-200/80"
          >
            {detailed ? t('chat.detailLess') : t('chat.detailMore')}
          </button>
        </div>

        <div className="space-y-2.5">
          {turns.map((turn, turnIndex) => {
            const key = turn.items[0]!.id
            const answer = turnAnswer(turn.items)
            const idle = isIdleDoneTurn(turn.items)

            if (!isAgentStepGroup(turn) && !answer) {
              prevAt = turn.items.at(-1)!.at
              return (
                <div key={key} className="space-y-2.5">
                  {turn.items.map((event) => (
                    <Ungrouped key={event.id} event={event} detailed={detailed} trace={runTrace} running={running} />
                  ))}
                </div>
              )
            }

            if (idle && seenAnswer) {
              prevAt = turn.items.at(-1)!.at
              if (!detailed) return null
              return (
                <p key={key} className="px-1 text-[12px] text-neutral-400">
                  {t('chat.waitingTask')}
                </p>
              )
            }

            const process = turnProcessItems(turn.items)
            const showStep = process.some(
              (event) => event.variant === 'step' || event.variant === 'tool' || event.variant === 'error' || event.variant === 'success' || event.variant === 'network'
            )
            if (showStep) stepNo += 1
            const url = [...process].reverse().map(navigatedUrl).find(Boolean) ?? null
            const showAnswer = Boolean(answer)
            if (showAnswer) seenAnswer = true
            if (!showStep && !showAnswer && !url) {
              prevAt = turn.items.at(-1)!.at
              return null
            }
            const card = (
              <div key={key} className="space-y-2">
                {showStep ? (
                  <StepCard
                    stepNo={stepNo}
                    group={{ ...turn, items: process }}
                    detailed={detailed}
                    prevAt={prevAt}
                    onRequeue={onRequeue}
                  />
                ) : null}
                {showAnswer && answer && !running ? <ResultCard event={answer} trace={runTrace} /> : null}
                {showAnswer && !running ? <DoneBar ok /> : null}
                {url ? <NavChip url={url} /> : null}
              </div>
            )
            prevAt = turn.items.at(-1)!.at
            const showFeedAd = turnIndex === 0 && showAnswer && !running
            return (
              <Fragment key={key}>
                {card}
                {showFeedAd ? (
                  <AdBanner surface="agentFeed" size="compact" className="my-1" />
                ) : null}
              </Fragment>
            )
          })}

          {[...childrenByParent.entries()].map(([parentRunId, childEvents]) => (
            <details
              key={parentRunId}
              className="rounded-2xl border border-violet-200 bg-violet-50/80 px-3 py-2 text-sm text-violet-950"
            >
              <summary className="cursor-pointer font-medium">
                {t('chat.messageList.childTaskSummary', { count: childEvents.length })}
              </summary>
              <div className="mt-2 space-y-2">
                {childEvents.map((event) => (
                  <Ungrouped key={event.id} event={event} detailed={detailed} trace={runTrace} running={running} />
                ))}
              </div>
            </details>
          ))}

          {topVideos && topVideos.length > 0 ? (
            <article className="rounded-2xl border border-emerald-200 bg-emerald-50/90 px-3 py-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <span className="rounded-md bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
                  {resultsMarked
                    ? t('chat.messageList.markedResults')
                    : t('chat.messageList.extractedResults')}
                </span>
                <span className="text-xs text-emerald-900">
                  {t('chat.messageList.itemCount', { count: topVideos.length })}
                </span>
              </div>
              {resultsStale ? (
                <p className="mb-2 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs text-amber-900">
                  {t('chat.messageList.resultsStale')}
                </p>
              ) : null}
              {listWarnings?.offscreen?.length ? (
                <p className="mb-2 text-xs text-amber-800">
                  {t('chat.messageList.offscreen', {
                    list: listWarnings.offscreen.join(locale === 'zh-CN' ? '、' : ', '),
                  })}
                </p>
              ) : null}
              {listWarnings?.missed?.length ? (
                <p className="mb-2 text-xs text-red-800">
                  {t('chat.messageList.missed', {
                    list: listWarnings.missed.join(locale === 'zh-CN' ? '、' : ', '),
                  })}
                </p>
              ) : null}
              {listWarnings?.shortfall ? (
                <p className="mb-2 text-xs text-amber-800">
                  {t('chat.messageList.shortfall', { message: listWarnings.shortfall })}
                </p>
              ) : null}
              <ol className={`space-y-2 text-sm leading-relaxed ${wide ? 'grid gap-2 sm:grid-cols-2' : ''}`}>
                {topVideos.map((video, index) => {
                  const { headline, detail } = formatListItem(video, index + 1)
                  return (
                    <li key={`${video.label}-${video.index}`}>
                      <button
                        type="button"
                        className="w-full rounded-md border border-emerald-100 bg-white/80 px-2.5 py-2 text-left hover:bg-white disabled:opacity-80"
                        onClick={() => resultsMarked && onFocusVideo?.(video)}
                        disabled={!resultsMarked}
                      >
                        <div className="font-medium text-foreground">{headline}</div>
                        {detail ? (
                          <div className="mt-1 whitespace-pre-wrap text-xs text-muted-foreground">{detail}</div>
                        ) : null}
                      </button>
                    </li>
                  )
                })}
              </ol>
            </article>
          ) : null}

          {runOutcome && !running && !['waiting', 'success'].includes(runOutcome.kind) ? (
            <article
              data-testid="run-outcome"
              className={`rounded-2xl border px-3 py-3 text-sm select-text ${OUTCOME_STYLES[runOutcome.kind]}`}
            >
              <strong>{runOutcome.title}</strong>
              <CollapsibleText text={runOutcome.message} className="mt-1" />
              {runOutcome.optionsSection ? (
                <button
                  type="button"
                  className="mt-2 block text-sm font-medium underline underline-offset-2 hover:opacity-80"
                  onClick={() => void openOptionsPage(runOutcome.optionsSection)}
                >
                  {t('chat.runOutcome.openSettings')}
                </button>
              ) : null}
            </article>
          ) : null}

          {showThinking ? (
            <div className="sticky bottom-0 z-10 bg-gradient-to-t from-background from-60% to-transparent pb-1 pt-3">
              <ThinkingChip
                detail={thinkingDetail}
                reasoning={thinkingReasoning}
                feed={liveFeed}
              />
              <AdBanner surface="agentThinking" size="compact" className="mt-1.5" />
            </div>
          ) : null}
        </div>

        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function Ungrouped({
  event,
  detailed,
  trace,
  running,
}: {
  event: RecordView
  detailed: boolean
  trace?: RunTrace
  running?: boolean
}) {
  if (event.variant === 'tools' && event.toolCatalog?.length) {
    return <ToolCatalogPanel catalog={event.toolCatalog} />
  }
  if (event.variant === 'user' || event.variant === 'task') return <UserBubble event={event} />
  if (event.variant === 'question') return <QuestionBubble event={event} />
  if (event.variant === 'result' && !running) return <ResultCard event={event} trace={trace} />
  if (event.variant === 'result') return null
  if (event.variant === 'system' && !detailed && !isContextView(event)) return null
  return <MessageCard event={event} />
}
