import type { AgentUiKitClassNames } from "./types";

/**
 * Default styling assumes the host Tailwind theme defines `brand-*`, `ink-*`,
 * `surface-*`, `warn-*`, `danger-*`, and `animate-agent-think` (see README).
 */
export const defaultAgentUiKitClassNames: AgentUiKitClassNames = {
  avatar:
    "inline-flex shrink-0 items-center justify-center rounded-full bg-brand-600 font-semibold tracking-tight text-white shadow-brand",
  avatarThinking:
    "animate-agent-think ring-2 ring-brand-300/60 ring-offset-1 ring-offset-brand-50",
  thinkingPill:
    "inline-flex animate-fade-in items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-100",
  thinkingInline: "inline-flex items-center gap-2 text-xs font-medium text-ink-700",
  thinkingDots: "inline-flex w-[1.1em] items-end gap-[2px] pb-[1px]",
  queueRoot: "shrink-0 border-t border-surface-border bg-surface/80 px-2.5 py-2 backdrop-blur",
  queueHeaderButton: "flex w-full items-center gap-2 text-left text-xs text-ink-600",
  queueTitle: "font-semibold text-ink-800",
  queueBadge: "badge badge-neutral tabular-nums",
  queueHint: "min-w-0 flex-1 truncate text-ink-500",
  queueChevron: "text-ink-500",
  queuePriorityBanner: "rounded-lg bg-warn-50 px-2.5 py-2 text-xs ring-1 ring-inset ring-warn-100",
  queuePriorityTitle: "font-medium text-warn-900",
  queuePriorityClear: "font-medium text-warn-700 hover:text-warn-900",
  queuePriorityHint: "mt-1 text-warn-700",
  queueRow:
    "group flex items-start gap-1.5 rounded-lg bg-surface-sunken px-2 py-2 text-xs ring-1 ring-inset ring-surface-border transition",
  queueRowDragging: "opacity-40",
  queueRowDropTarget: "ring-2 ring-brand-300",
  queueGrip: "mt-0.5 shrink-0 text-ink-400 cursor-grab active:cursor-grabbing",
  queueIndex: "mt-0.5 shrink-0 font-mono tabular-nums text-ink-500",
  queueBody: "min-w-0 flex-1 whitespace-pre-wrap text-ink-700",
  queueEditArea:
    "min-w-0 flex-1 resize-y rounded-md border border-surface-border bg-surface px-2 py-1.5 text-xs leading-relaxed text-ink-800 shadow-xs focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-200",
  queueIconButton:
    "flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-ink-500 transition hover:bg-surface-muted hover:text-ink-800 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300",
  queueIconButtonDanger: "hover:text-danger-600",
  queueIconButtonAccent: "text-brand-700 hover:bg-brand-50 hover:text-brand-800",
};
