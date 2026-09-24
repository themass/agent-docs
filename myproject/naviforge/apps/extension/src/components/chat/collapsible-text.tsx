import { useState, type ReactNode } from 'react'

import { cn } from '../../lib/cn'

export const DEFAULT_COLLAPSE_CHARS = 480

export function collapsedPreview(text: string, maxChars: number, expanded: boolean): string {
  if (expanded || text.length <= maxChars) return text
  return `${text.slice(0, maxChars)}…`
}

export function shouldCollapseText(text: string, maxChars: number = DEFAULT_COLLAPSE_CHARS): boolean {
  return text.length > maxChars
}

export function CollapseToggle({
  expanded,
  totalChars,
  onToggle,
  className,
}: {
  expanded: boolean
  totalChars: number
  onToggle: () => void
  className?: string
}) {
  return (
    <button
      type="button"
      className={cn(
        'mb-1 text-[12px] font-medium text-neutral-500 hover:text-neutral-800',
        className
      )}
      onClick={onToggle}
    >
      {expanded ? '收起' : `展开全文（${totalChars} 字）`}
    </button>
  )
}

export function CollapsibleText({
  text,
  maxChars = DEFAULT_COLLAPSE_CHARS,
  className,
  pre = false,
}: {
  text: string
  maxChars?: number
  className?: string
  pre?: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const foldable = shouldCollapseText(text, maxChars)
  const visible = collapsedPreview(text, maxChars, expanded)

  return (
    <div className={cn('min-w-0', className)}>
      {foldable ? (
        <CollapseToggle
          expanded={expanded}
          totalChars={text.length}
          onToggle={() => setExpanded((value) => !value)}
        />
      ) : null}
      {pre ? (
        <pre className="max-h-[28rem] overflow-auto whitespace-pre-wrap break-words text-[12px] leading-relaxed text-neutral-700">
          {visible}
        </pre>
      ) : (
        <p className="leading-relaxed break-words whitespace-pre-wrap">{visible}</p>
      )}
    </div>
  )
}

export function CollapsibleBlock({
  text,
  maxChars = DEFAULT_COLLAPSE_CHARS,
  className,
  children,
}: {
  text: string
  maxChars?: number
  className?: string
  children: (visible: string) => ReactNode
}) {
  const [expanded, setExpanded] = useState(false)
  const foldable = shouldCollapseText(text, maxChars)
  const visible = collapsedPreview(text, maxChars, expanded)

  return (
    <div className={cn('min-w-0', className)}>
      {foldable ? (
        <CollapseToggle
          expanded={expanded}
          totalChars={text.length}
          onToggle={() => setExpanded((value) => !value)}
        />
      ) : null}
      {children(visible)}
    </div>
  )
}
