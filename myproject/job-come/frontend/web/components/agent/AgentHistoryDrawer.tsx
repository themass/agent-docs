"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import { sessionListMeta, sessionListTitle } from "@/lib/agent-session-display";
import type { AgentSessionListItem } from "@/lib/api/agent";
import { useAuth } from "@/lib/auth/AuthProvider";
import { copyToClipboard } from "@/lib/clipboard";

type Props = {
  open: boolean;
  sessions: AgentSessionListItem[];
  activeId: string | null;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
};

/** Copies `text` without letting the click bubble into the row's onSelect. */
function CopyIdButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  return (
    <button
      type="button"
      title="复制 session id"
      onClick={async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const ok = await copyToClipboard(text);
        if (ok) {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        }
      }}
      className="shrink-0 rounded px-1 py-0.5 text-micro text-ink-400 transition hover:bg-ink-100 hover:text-ink-700"
    >
      {copied ? "已复制" : "复制"}
    </button>
  );
}

export function AgentHistoryDrawer({ open, sessions, activeId, onClose, onSelect, onNew }: Props) {
  const { context } = useAuth();
  const isAdmin = context?.capabilities.includes("admin") ?? false;

  const sorted = useMemo(
    () => [...sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [sessions],
  );

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-40 flex">
      <button
        type="button"
        className="flex-1 animate-fade-in bg-ink-900/25 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="关闭历史"
      />
      <aside className="flex h-full w-[min(18rem,88vw)] animate-fade-in flex-col border-l border-surface-border bg-surface shadow-pop">
        <div className="flex items-center justify-between border-b border-surface-border px-3 py-2.5">
          <p className="text-sm font-semibold text-ink-900">历史会话</p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onNew}
              className="btn btn-sm btn-ghost text-brand-700 hover:bg-brand-50 hover:text-brand-800"
            >
              新对话
            </button>
            <button type="button" onClick={onClose} className="btn btn-sm btn-ghost w-7 px-0">
              ×
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {sorted.length === 0 ? (
            <p className="px-2 py-8 text-center text-xs text-ink-500">暂无历史会话</p>
          ) : (
            <ul className="space-y-1">
              {sorted.map((session) => {
                const active = session.id === activeId;
                return (
                  <li key={session.id}>
                    <div
                      className={`group w-full rounded-lg px-3 py-2.5 text-left transition ${
                        active
                          ? "bg-brand-50 text-brand-900 ring-1 ring-inset ring-brand-200"
                          : "text-ink-700 hover:bg-ink-50"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          onSelect(session.id);
                          onClose();
                        }}
                        className="block w-full select-text text-left"
                      >
                        <p className="line-clamp-2 text-xs font-medium leading-snug">
                          {sessionListTitle(session)}
                        </p>
                        <p className={`mt-0.5 text-micro ${active ? "text-brand-600" : "text-ink-500"}`}>
                          {sessionListMeta(session)}
                        </p>
                      </button>
                      {isAdmin ? (
                        <div className="mt-0.5 flex items-center gap-1.5">
                          <p className="select-text truncate font-mono text-micro text-ink-400">
                            {session.id}
                          </p>
                          <CopyIdButton text={session.id} />
                          <Link
                            href={`/admin/sessions?session_id=${encodeURIComponent(session.id)}`}
                            onClick={(e) => e.stopPropagation()}
                            title="在管理后台查看这个会话"
                            className="shrink-0 rounded px-1 py-0.5 text-micro text-brand-600 transition hover:bg-brand-50 hover:text-brand-800"
                          >
                            审计 →
                          </Link>
                        </div>
                      ) : null}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
}
