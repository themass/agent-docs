"use client";

import Link from "next/link";

import { AgentMark } from "@/components/agent/AgentMark";
import { AgentReplyLocaleSelect } from "@/components/agent/AgentReplyLocaleSelect";
import type { AgentReplyLocale } from "@/lib/agent-locale";
import type { AgentSessionListItem } from "@/lib/api/agent";

type Props = {
  sessionId: string | null;
  busy: boolean;
  sessions: AgentSessionListItem[];
  statusDetail?: string | null;
  disabled?: boolean;
  replyLocale: AgentReplyLocale;
  onReplyLocaleChange: (locale: AgentReplyLocale) => void;
  onNew: () => void;
  onOpenHistory: () => void;
};

export function AgentHeader({
  sessionId,
  busy,
  sessions,
  statusDetail,
  disabled,
  replyLocale,
  onReplyLocaleChange,
  onNew,
  onOpenHistory,
}: Props) {
  const detail = statusDetail?.trim() || (sessionId ? `会话 ${sessionId.slice(0, 10)}…` : "新对话");

  return (
    <header className="relative flex h-11 shrink-0 items-center justify-between gap-2 border-b border-slate-200/70 bg-white px-3">
      <div className="flex min-w-0 items-center gap-2">
        <AgentMark size={24} />
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="text-[12px] font-semibold leading-none text-slate-900">Agent</p>
            <span
              className={`size-1.5 rounded-full ${busy ? "bg-sky-500 animate-pulse" : "bg-slate-300"}`}
              title={busy ? "运行中" : "空闲"}
            />
            {busy ? (
              <span className="rounded-full bg-sky-50 px-1.5 py-0.5 text-[10px] font-medium text-sky-700">
                运行中
              </span>
            ) : null}
          </div>
          <p className="mt-0.5 truncate text-[10px] text-slate-400" title={detail}>
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
            <Link
              href="/admin/sessions"
              title="会话审计（完整 prompt / 工具 / checkpoint）"
              className="inline-flex size-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
            </Link>
            <button
              type="button"
              onClick={onNew}
              title="新对话"
              className="inline-flex size-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v14M5 12h14" />
              </svg>
            </button>
            <button
              type="button"
              onClick={onOpenHistory}
              title="历史会话"
              className="relative inline-flex size-8 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-100 hover:text-slate-800"
            >
              <svg className="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              {sessions.length > 0 ? (
                <span className="absolute -right-0.5 -top-0.5 min-w-[14px] rounded-full bg-slate-900 px-1 text-center text-[9px] font-medium text-white">
                  {sessions.length > 9 ? "9+" : sessions.length}
                </span>
              ) : null}
            </button>
          </>
        ) : null}
      </div>
    </header>
  );
}
