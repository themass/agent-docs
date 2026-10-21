"use client";

import Link from "next/link";

import { AgentMark } from "@/components/agent/AgentMark";
import { AgentReplyLocaleSelect } from "@/components/agent/AgentReplyLocaleSelect";
import { truncateAgentHeaderLabel } from "@/lib/agent-session-display";
import type { AgentReplyLocale } from "@/lib/agent-locale";
import type { AgentSessionListItem } from "@/lib/api/agent";
import { useAuth } from "@/lib/auth/AuthProvider";
import { ZHOUKA_NAME } from "@/lib/brand";

type Props = {
  sessionId: string | null;
  busy: boolean;
  sessions: AgentSessionListItem[];
  statusDetail?: string | null;
  sessionSubtitle?: string | null;
  disabled?: boolean;
  replyLocale: AgentReplyLocale;
  onReplyLocaleChange: (locale: AgentReplyLocale) => void;
  onNew: () => void;
  onOpenHistory: () => void;
  /** Omitted when the panel cannot be collapsed (unified layout). */
  onCollapse?: () => void;
};

export function AgentHeader({
  sessionId,
  busy,
  sessions,
  statusDetail,
  sessionSubtitle,
  disabled,
  replyLocale,
  onReplyLocaleChange,
  onNew,
  onOpenHistory,
  onCollapse,
}: Props) {
  const { context } = useAuth();
  const isAdmin = context?.capabilities.includes("admin") ?? false;

  const subtitleFull =
    sessionSubtitle?.trim() || (sessionId ? "当前对话" : "新对话");
  const detail = statusDetail?.trim()
    ? statusDetail.trim()
    : truncateAgentHeaderLabel(subtitleFull);
  const detailTitle = statusDetail?.trim() || sessionSubtitle?.trim() || detail;

  return (
    <header className="relative flex h-12 shrink-0 items-center justify-between gap-2 border-b border-surface-border bg-surface px-3">
      <div className="flex min-w-0 flex-1 items-center gap-2 pr-1">
        <AgentMark size={24} className="shrink-0" />
        <div className="min-w-[2.75rem] shrink-0">
          <div className="flex items-center gap-1.5 whitespace-nowrap">
            <p className="text-xs font-semibold leading-none text-ink-900">{ZHOUKA_NAME}</p>
            <span
              className={`size-1.5 shrink-0 rounded-full ${busy ? "bg-brand-500 animate-pulse" : "bg-ink-300"}`}
              title={busy ? "运行中" : "空闲"}
            />
            {busy ? <span className="badge badge-brand shrink-0">运行中</span> : null}
          </div>
          <p className="mt-0.5 truncate text-micro text-ink-500" title={detailTitle}>
            {detail}
          </p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-0.5">
        <AgentReplyLocaleSelect
          value={replyLocale}
          onChange={onReplyLocaleChange}
          disabled={disabled}
        />
        {!disabled ? (
          <>
            {isAdmin ? (
              <Link
                href="/admin/sessions"
                title="会话审计（prompt / 工具 / checkpoint）"
                className="btn size-8 shrink-0 btn-ghost p-0"
              >
                <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
              </Link>
            ) : null}
            <button
              type="button"
              onClick={onNew}
              title="新对话"
              className="btn size-8 shrink-0 btn-ghost p-0"
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onOpenHistory}
              title="历史会话"
              className="btn relative size-8 shrink-0 btn-ghost p-0"
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {sessions.length > 0 ? (
                <span className="absolute -right-0.5 -top-0.5 min-w-[14px] rounded-full bg-brand-600 px-1 text-center text-micro font-medium tabular-nums text-white">
                  {sessions.length > 9 ? "9+" : sessions.length}
                </span>
              ) : null}
            </button>
          </>
        ) : null}
        {onCollapse ? (
          <button
            type="button"
            onClick={onCollapse}
            title={`收起${ZHOUKA_NAME}，把空间让给简历`}
            className="btn size-8 shrink-0 btn-ghost p-0"
          >
            <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
            <span className="sr-only">收起{ZHOUKA_NAME}，把空间让给简历</span>
          </button>
        ) : null}
      </div>
    </header>
  );
}
