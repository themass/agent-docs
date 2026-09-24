import { useEffect, useRef } from 'react'

import { cn } from '../../lib/cn'
import {
  filterSlashCommands,
  slashCommandLabel,
  slashCommandMenuLabel,
  type SlashCommandDef,
} from './composer-slash-registry'

export function SlashCommandChip({
  command,
  onClear,
}: {
  command: SlashCommandDef
  onClear?: () => void
}) {
  return (
    <div className="flex items-start gap-2 border-b border-border/50 px-3 py-2">
      <div
        className="inline-flex flex-wrap items-center gap-2 rounded-md border border-border/80 bg-muted/50 px-2 py-1 font-mono text-[12px] leading-5 text-foreground shadow-[inset_0_1px_0_rgba(255,255,255,0.6)]"
        title={command.hint}
      >
        <span className="font-semibold text-red-600">{slashCommandLabel(command)}</span>
        {command.argumentHint ? (
          <span className="text-[10px] font-normal text-muted-foreground">{command.argumentHint}</span>
        ) : null}
      </div>
      {onClear ? (
        <button
          type="button"
          className="mt-0.5 text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          onClick={onClear}
        >
          移除
        </button>
      ) : null}
    </div>
  )
}

export function SlashCommandMenu({
  query,
  activeIndex,
  registry,
  onPick,
  onHover,
}: {
  query: string
  activeIndex: number
  registry: SlashCommandDef[]
  onPick: (command: SlashCommandDef) => void
  onHover: (index: number) => void
}) {
  const items = filterSlashCommands(query, registry)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>(`[data-slash-index="${activeIndex}"]`)
    el?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  if (!items.length) {
    return (
      <div className="absolute bottom-full left-0 z-30 mb-2 w-[min(100%,18rem)] rounded-xl border border-border/80 bg-background px-3 py-2 text-[12px] text-muted-foreground shadow-lg">
        没有匹配的命令
      </div>
    )
  }

  return (
    <div
      ref={listRef}
      role="listbox"
      aria-label="斜杠命令"
      className="absolute bottom-full left-0 z-30 mb-2 max-h-56 w-[min(100%,20rem)] overflow-y-auto rounded-xl border border-border/80 bg-background py-1 shadow-lg"
    >
      {items.map((item, index) => {
        const { label, hitStart, hitEnd } = slashCommandMenuLabel(item, query)
        const before = label.slice(0, hitStart)
        const hit = label.slice(hitStart, hitEnd)
        const after = label.slice(hitEnd)
        return (
          <button
            key={item.name}
            type="button"
            role="option"
            data-slash-index={index}
            aria-selected={index === activeIndex}
            className={cn(
              'flex w-full flex-col gap-0.5 px-3 py-2 text-left transition-colors',
              index === activeIndex ? 'bg-muted' : 'hover:bg-muted/70'
            )}
            onMouseEnter={() => onHover(index)}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onPick(item)}
          >
            <span className="font-mono text-[12px] leading-4">
              <span className="text-muted-foreground">/</span>
              {hit ? (
                <>
                  <span className="text-foreground">{before}</span>
                  <span className="font-semibold text-red-600">{hit}</span>
                  <span className="text-foreground">{after}</span>
                </>
              ) : (
                <span className="text-foreground">{label}</span>
              )}
              {item.argumentHint ? (
                <span className="ml-1 text-[10px] font-normal text-muted-foreground">
                  {item.argumentHint}
                </span>
              ) : null}
            </span>
            <span className="text-[11px] text-muted-foreground">{item.hint}</span>
          </button>
        )
      })}
    </div>
  )
}

/** Mirror textarea — menu: red query; locked: command chip + args. */
export function SlashInputHighlight({
  text,
  mode,
}: {
  text: string
  mode: 'menu' | 'locked' | null
}) {
  if (!text.startsWith('/') || !mode) return null
  const mirrorClass =
    'pointer-events-none absolute inset-0 overflow-hidden whitespace-pre-wrap break-words px-3 pt-2 pb-0 font-mono text-[14px] leading-5'

  if (mode === 'menu') {
    const query = text.slice(1)
    return (
      <div aria-hidden className={mirrorClass}>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold text-red-600">{query}</span>
      </div>
    )
  }

  const match = text.match(/^(\/(?:skill:[\w.-]+|[\w-]+))([\s\S]*)$/)
  if (!match) return null
  const token = match[1] ?? '/'
  const rest = match[2] ?? ''
  return (
    <div aria-hidden className={mirrorClass}>
      <span
        className={cn(
          'rounded-[5px] bg-red-50 font-semibold text-red-600',
          'ring-1 ring-inset ring-red-300/90 shadow-[0_1px_0_rgba(255,255,255,0.7)_inset]'
        )}
      >
        {token}
      </span>
      <span className="text-foreground">{rest}</span>
    </div>
  )
}

export function slashMenuItems(query: string, registry: SlashCommandDef[]): SlashCommandDef[] {
  return filterSlashCommands(query, registry)
}
