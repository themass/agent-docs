import { X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import type { ContextBlockMetric, ContextBreakdown } from '@naviforge/context-metrics'
import { contextUsageRatio, runBudgetRatio } from '@naviforge/context-metrics'

import { useI18n } from '../../i18n/index.js'
import { rollupContextAuditBlocks } from './audit-blocks.js'
import { formatContextMeterLabel, formatContextTokens } from './types.js'

const BLOCK_ORDER = [
  'system',
  'skill_catalog',
  'tools',
  'skills',
  'task',
  'reply_language',
  'scope',
  'thread',
  'snapshot',
  'browser',
  'url',
  'title',
  'frames',
  'network',
  'trace',
  'instruction',
] as const

const BLOCK_COLORS: Record<string, string> = {
  system: 'bg-sky-500',
  skill_catalog: 'bg-violet-500',
  tools: 'bg-orange-500',
  mcp_tools: 'bg-fuchsia-500',
  loaded_skills: 'bg-purple-500',
  user_prompt: 'bg-emerald-500',
  thread: 'bg-pink-500',
  page: 'bg-cyan-500',
  network: 'bg-amber-500',
  trace: 'bg-yellow-600',
  skills: 'bg-purple-500',
  task: 'bg-emerald-500',
  reply_language: 'bg-teal-500',
  scope: 'bg-indigo-400',
  snapshot: 'bg-cyan-500',
  browser: 'bg-slate-400',
  url: 'bg-slate-500',
  title: 'bg-slate-500',
  frames: 'bg-slate-500',
  instruction: 'bg-lime-600',
}

const FALLBACK_COLORS = [
  'bg-blue-500',
  'bg-violet-500',
  'bg-orange-500',
  'bg-emerald-500',
  'bg-pink-500',
  'bg-cyan-500',
] as const

function blockColor(id: string, index: number): string {
  return BLOCK_COLORS[id] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length]!
}

function ringStrokeClass(ratio: number, pressured?: boolean): string {
  if (pressured || ratio >= 0.92) return 'stroke-amber-500'
  if (ratio >= 0.8) return 'stroke-orange-500'
  return 'stroke-muted-foreground/70'
}

function ContextRing({
  ratio,
  pressured,
  size = 16,
}: {
  ratio: number
  pressured?: boolean
  size?: number
}) {
  const stroke = 2
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const offset = c * (1 - Math.min(1, Math.max(0, ratio)))
  const color = ringStrokeClass(ratio, pressured)
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90 shrink-0" aria-hidden>
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        className="stroke-border/80"
        strokeWidth={stroke}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        className={color}
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={c}
        strokeDashoffset={offset}
      />
    </svg>
  )
}

function sortBlocks(blocks: ContextBlockMetric[]): ContextBlockMetric[] {
  const order = new Map(BLOCK_ORDER.map((id, index) => [id, index]))
  return [...blocks].sort((a, b) => {
    const ai = order.get(a.id as (typeof BLOCK_ORDER)[number]) ?? 99
    const bi = order.get(b.id as (typeof BLOCK_ORDER)[number]) ?? 99
    if (ai !== bi) return ai - bi
    return b.tokens - a.tokens
  })
}

function SegmentedContextBar({
  blocks,
  totalTokens,
  limitTokens,
}: {
  blocks: ContextBlockMetric[]
  totalTokens: number
  limitTokens: number
}) {
  const filledPct = limitTokens > 0 ? Math.min(100, (totalTokens / limitTokens) * 100) : 0
  const segments = blocks.filter((block) => block.tokens > 0)
  if (!segments.length) {
    return <div className="h-1.5 w-full rounded-full bg-muted" />
  }
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className="flex h-full min-w-0" style={{ width: `${filledPct}%` }}>
        {segments.map((block, index) => {
          const share = totalTokens > 0 ? (block.tokens / totalTokens) * 100 : 0
          if (share <= 0) return null
          return (
            <div
              key={block.id}
              className={`h-full min-w-[2px] ${blockColor(block.id, index)}`}
              style={{ width: `${share}%` }}
              title={`${block.label}: ~${formatContextTokens(block.tokens)}`}
            />
          )
        })}
      </div>
    </div>
  )
}

function ContextAuditPanel({
  breakdown,
  runTotal,
  runTokenBudget,
  onClose,
}: {
  breakdown: ContextBreakdown
  runTotal?: number
  runTokenBudget?: number
  onClose: () => void
}) {
  const { t } = useI18n()
  const inputRatio = contextUsageRatio(breakdown)
  const pct = Math.round(inputRatio * 100)
  const used = formatContextTokens(breakdown.grandTotalTokens)
  const limit = formatContextTokens(breakdown.limitInputTokens)
  const blocks = useMemo(
    () =>
      rollupContextAuditBlocks(breakdown, {
        system: t('chat.contextGroup.system'),
        skill_catalog: t('chat.contextGroup.skillCatalog'),
        tools: t('chat.contextGroup.tools'),
        mcp_tools: t('chat.contextGroup.mcp'),
        loaded_skills: t('chat.contextGroup.loadedSkills'),
        user_prompt: t('chat.contextGroup.userPrompt'),
        thread: t('chat.contextGroup.thread'),
        page: t('chat.contextGroup.page'),
        network: t('chat.contextGroup.network'),
        trace: t('chat.contextGroup.trace'),
      }),
    [breakdown, t]
  )
  const budgetRatio =
    runTokenBudget && runTokenBudget > 0 && runTotal != null
      ? Math.min(1, runTotal / runTokenBudget)
      : runBudgetRatio(breakdown)

  return (
    <div className="absolute bottom-full right-0 z-50 mb-1.5 w-[min(22rem,calc(100vw-1rem))] overflow-hidden rounded-lg border border-zinc-700/80 bg-zinc-900 text-zinc-100 shadow-2xl shadow-black/40">
      <div className="flex items-center justify-between gap-2 border-b border-zinc-700/70 px-3 py-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium leading-none text-zinc-50">{t('chat.contextAuditTitle')}</p>
          <p className="mt-1 text-[10px] leading-none text-zinc-400">
            {t('chat.contextAuditTokens', { used, limit })}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <span className="text-[11px] font-medium tabular-nums leading-none text-zinc-200">{pct}%</span>
          <button
            type="button"
            className="inline-flex size-5 items-center justify-center rounded text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-zinc-100"
            aria-label={t('chat.contextAuditClose')}
            onClick={onClose}
          >
            <X className="size-3" />
          </button>
        </div>
      </div>

      <div className="space-y-2 px-3 py-2.5">
        <SegmentedContextBar
          blocks={blocks}
          totalTokens={breakdown.grandTotalTokens}
          limitTokens={breakdown.limitInputTokens}
        />

        <ul className="max-h-56 space-y-0 divide-y divide-zinc-800 overflow-y-auto overscroll-contain [scrollbar-gutter:stable] pr-2.5 text-[11px] leading-tight">
          {blocks.map((block, index) => (
            <li key={block.id} className="flex items-center justify-between gap-2 py-1.5 first:pt-0 last:pb-0">
              <span className="flex min-w-0 items-center gap-1.5 text-zinc-200">
                <span className={`size-1.5 shrink-0 rounded-[2px] ${blockColor(block.id, index)}`} />
                <span className="truncate" title={`${block.chars} chars`}>
                  {block.label}
                </span>
              </span>
              <span className="shrink-0 font-mono text-[10px] tabular-nums text-zinc-400">
                {formatContextTokens(block.tokens)}
              </span>
            </li>
          ))}
        </ul>

        {breakdown.compaction ? (
          <p className="text-[10px] leading-snug text-amber-400">
            {t('chat.contextCompacted', {
              before: formatContextTokens(breakdown.compaction.beforeTokens),
              after: formatContextTokens(breakdown.compaction.afterTokens),
            })}
          </p>
        ) : breakdown.pressured ? (
          <p className="text-[10px] leading-snug text-amber-400">{t('chat.contextPressured')}</p>
        ) : null}

        {runTokenBudget != null && runTokenBudget > 0 ? (
          <div className="border-t border-zinc-800 pt-2">
            <div className="mb-0.5 flex items-center justify-between text-[10px] leading-none text-zinc-400">
              <span>{t('chat.contextRunBudget')}</span>
              <span className="font-mono tabular-nums">
                ~{formatContextTokens(runTotal ?? breakdown.runTotalTokens)} /{' '}
                {formatContextTokens(runTokenBudget)}
              </span>
            </div>
            <div className="h-0.5 w-full overflow-hidden rounded-full bg-zinc-800">
              <div className="h-full bg-violet-500" style={{ width: `${Math.round(budgetRatio * 100)}%` }} />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function ContextMeterBody({
  breakdown,
  runTotal,
  runTokenBudget,
}: {
  breakdown: ContextBreakdown
  runTotal?: number
  runTokenBudget?: number
}) {
  const inputRatio = contextUsageRatio(breakdown)
  const budgetRatio =
    runTokenBudget && runTokenBudget > 0 && runTotal != null
      ? Math.min(1, runTotal / runTokenBudget)
      : runBudgetRatio(breakdown)

  const barColor =
    inputRatio >= 0.9 ? 'bg-amber-500' : inputRatio >= 0.75 ? 'bg-yellow-500' : 'bg-sky-500'

  return (
    <>
      <div className="flex items-center justify-between gap-2 text-muted-foreground">
        <span className="font-medium text-foreground/90">{formatContextMeterLabel(breakdown)}</span>
        {breakdown.compaction ? (
          <span className="text-amber-700" title="上下文已压缩">
            −{Math.round((1 - breakdown.compaction.afterTokens / breakdown.compaction.beforeTokens) * 100)}%
          </span>
        ) : null}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${barColor}`} style={{ width: `${Math.round(inputRatio * 100)}%` }} />
      </div>
      <div className="max-h-48 space-y-1 overflow-y-auto overscroll-contain [scrollbar-gutter:stable] pr-2.5 text-[10px] text-muted-foreground">
        {sortBlocks(breakdown.blocks).map((block, index) => (
          <div key={block.id} className="flex items-baseline justify-between gap-3">
            <span className="flex min-w-0 items-center gap-1.5 truncate text-foreground/80" title={`${block.chars} chars`}>
              <span className={`size-1.5 shrink-0 rounded-sm ${blockColor(block.id, index)}`} />
              {block.label}
            </span>
            <span className="shrink-0 tabular-nums">~{formatContextTokens(block.tokens)}</span>
          </div>
        ))}
      </div>
      {runTokenBudget != null && runTokenBudget > 0 ? (
        <div className="h-1 w-full overflow-hidden rounded-full bg-muted/60" title="Run token budget">
          <div className="h-full bg-violet-400" style={{ width: `${Math.round(budgetRatio * 100)}%` }} />
        </div>
      ) : null}
    </>
  )
}

export function ContextMeter({
  breakdown,
  runTotal,
  runTokenBudget,
  variant = 'inline',
  className = '',
  active = false,
}: {
  breakdown: ContextBreakdown | null
  runTotal?: number
  runTokenBudget?: number
  variant?: 'inline' | 'popover' | 'chip' | 'toolbar'
  className?: string
  /** Show toolbar chip while a run is in flight, before metrics records arrive. */
  active?: boolean
}) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [hover, setHover] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDoc = (event: MouseEvent): void => {
      if (rootRef.current?.contains(event.target as Node)) return
      setOpen(false)
    }
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    window.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (!breakdown) {
    if (runTotal == null) {
      if (!active || (variant !== 'toolbar' && variant !== 'chip')) return null
      return (
        <div ref={rootRef} className={`relative ${className}`}>
          <button
            type="button"
            className="inline-flex h-7 items-center gap-1 rounded-full px-1.5 text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
            aria-label={t('chat.contextPending')}
            title={t('chat.contextPending')}
            disabled
          >
            <ContextRing ratio={0} size={14} />
            <span className="max-w-[4.5rem] truncate font-mono text-[10px] tabular-nums text-muted-foreground/70">
              …
            </span>
          </button>
        </div>
      )
    }
    const budget = runTokenBudget ?? 0
    const ratio = budget > 0 ? Math.min(1, runTotal / budget) : 0
    const used = formatContextTokens(runTotal)
    const limit = budget > 0 ? formatContextTokens(budget) : '—'
    if (variant === 'toolbar' || variant === 'chip') {
      return (
        <div ref={rootRef} className={`relative ${className}`}>
          <button
            type="button"
            className="inline-flex h-7 items-center gap-1 rounded-full px-1.5 text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
            aria-label={budget > 0 ? `~${used} / ${limit} tokens` : `~${used} tokens`}
            title={budget > 0 ? `~${used} / ${limit} tokens` : `~${used} tokens`}
          >
            <ContextRing ratio={ratio} size={14} />
            <span className="max-w-[4.5rem] truncate font-mono text-[10px] tabular-nums">{used}</span>
          </button>
        </div>
      )
    }
    return (
      <div className={`text-[10px] text-muted-foreground ${className}`}>
        ~{used}
        {budget > 0 ? ` / ${limit}` : ''} tokens
      </div>
    )
  }

  const inputRatio = contextUsageRatio(breakdown)
  const pct = Math.round(inputRatio * 100)
  const used = formatContextTokens(breakdown.grandTotalTokens)
  const limit = formatContextTokens(breakdown.limitInputTokens)
  const compacted = Boolean(breakdown.compaction)
  const pressured = Boolean(breakdown.pressured)
  const hoverTitle = compacted
    ? t('chat.contextCompacted', {
        before: formatContextTokens(breakdown.compaction!.beforeTokens),
        after: formatContextTokens(breakdown.compaction!.afterTokens),
      })
    : pressured
      ? t('chat.contextPressured')
      : t('chat.contextUsed', { pct: String(pct) })

  if (variant === 'toolbar' || variant === 'chip') {
    return (
      <div
        ref={rootRef}
        className={`relative ${className}`}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
      >
        <button
          type="button"
          className="inline-flex size-7 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground"
          aria-expanded={open}
          aria-label={hoverTitle}
          onClick={() => setOpen((value) => !value)}
        >
          <ContextRing ratio={inputRatio} pressured={pressured && !compacted} />
        </button>

        {hover && !open ? (
          <div
            className="pointer-events-none absolute bottom-full right-0 z-50 mb-1.5 max-w-[14rem] rounded-md border border-border/80 bg-background px-2 py-1 text-[10px] leading-snug text-foreground shadow-md"
            role="tooltip"
          >
            {t('chat.contextUsed', { pct: String(pct) })} · ~{used}/{limit}
          </div>
        ) : null}

        {open ? (
          <ContextAuditPanel
            breakdown={breakdown}
            runTotal={runTotal}
            runTokenBudget={runTokenBudget}
            onClose={() => setOpen(false)}
          />
        ) : null}
      </div>
    )
  }

  if (variant === 'popover') {
    const barColor =
      inputRatio >= 0.92 ? 'bg-amber-500' : inputRatio >= 0.8 ? 'bg-orange-500' : 'bg-primary'

    return (
      <div ref={rootRef} className={`pointer-events-auto z-30 ${className}`}>
        <button
          type="button"
          className="flex max-w-[12rem] flex-col gap-0.5 rounded-lg border border-border/80 bg-background px-2.5 py-1.5 text-left shadow-md transition-colors hover:bg-muted/40"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          <span className="text-[10px] font-medium text-foreground">{t('chat.contextUsed', { pct: String(pct) })}</span>
          <span className="text-[10px] text-muted-foreground">
            ~{used} / {limit}
          </span>
          <span className="h-0.5 w-full overflow-hidden rounded-full bg-muted">
            <span className={`block h-full ${barColor}`} style={{ width: `${pct}%` }} />
          </span>
        </button>
        {open ? (
          <div className="absolute bottom-full right-0 z-40 mb-1.5 w-[min(16rem,calc(100vw-2rem))] space-y-1 rounded-md border border-border/80 bg-background p-2 text-[10px] shadow-lg">
            <ContextMeterBody breakdown={breakdown} runTotal={runTotal} runTokenBudget={runTokenBudget} />
          </div>
        ) : null}
      </div>
    )
  }

  return (
    <div className={`space-y-1 rounded-md border border-border/60 bg-background px-2 py-1.5 text-[10px] ${className}`}>
      <ContextMeterBody breakdown={breakdown} runTotal={runTotal} runTokenBudget={runTokenBudget} />
    </div>
  )
}
