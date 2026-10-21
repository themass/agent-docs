"use client";

import { AgentMark } from "@/components/agent/AgentMark";
import { ZHOUKA_NAME } from "@/lib/brand";

type Props = {
  onExpand: () => void;
  /** Agent is mid-run while collapsed, so the strip has to say so. */
  busy?: boolean;
  /** Unread assistant replies that arrived while collapsed. */
  unread?: number;
  /** Suppress the attention cue once the user has used the assistant. */
  hint?: boolean;
};

/**
 * The 44px strip the agent sidebar collapses into.
 *
 * It is a button, not a decorative edge: the whole strip is the hit target, because a
 * 44px column with a small icon in it invites clicking anywhere on the column.
 *
 * The sidebar itself is *not* unmounted when collapsed -- see `ResizableSplitPane`.
 * This component only draws the closed state.
 */
export function AgentRailHandle({ onExpand, busy = false, unread = 0, hint = true }: Props) {
  // The cue is for first-time discovery. Once there is something to come back to -- a
  // run in flight or a reply waiting -- the state itself is the reason to click, and an
  // idle animation next to it would compete with the badge that carries real news.
  const showHint = hint && !busy && unread === 0;

  return (
    <button
      type="button"
      onClick={onExpand}
      title={`展开${ZHOUKA_NAME}`}
      aria-label={
        busy
          ? `展开${ZHOUKA_NAME}（正在处理）`
          : unread > 0
            ? `展开${ZHOUKA_NAME}（${unread} 条新回复）`
            : `展开${ZHOUKA_NAME}，让它帮你改这份简历`
      }
      className="agent-rail-collapsed group flex h-full flex-col items-center gap-3 border-l border-surface-border bg-surface py-3 transition hover:bg-brand-50/60 focus-visible:bg-brand-50/60 focus-visible:outline-none"
    >
      <span className="relative shrink-0">
        <AgentMark size={28} className={showHint ? "animate-nudge-x" : ""} />
        {busy ? (
          <span
            className="absolute -right-0.5 -top-0.5 size-2.5 animate-pulse rounded-full bg-brand-500 ring-2 ring-surface"
            aria-hidden
          />
        ) : unread > 0 ? (
          <span
            className="absolute -right-1 -top-1 min-w-[16px] rounded-full bg-brand-600 px-1 text-center text-micro font-medium tabular-nums text-white ring-2 ring-surface"
            aria-hidden
          >
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </span>

      <span
        className={`agent-rail-label min-h-0 flex-1 overflow-hidden text-micro font-medium ${
          busy || unread > 0 ? "text-brand-700" : "text-ink-500 group-hover:text-brand-700"
        }`}
      >
        {busy ? "正在处理…" : unread > 0 ? "有新回复" : `点这里让${ZHOUKA_NAME}帮你改`}
      </span>

      {/* Affordance, not decoration: a chevron is what tells the user this opens. */}
      <svg
        className="size-4 shrink-0 text-ink-400 transition group-hover:text-brand-600"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        aria-hidden
      >
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
      </svg>
    </button>
  );
}
