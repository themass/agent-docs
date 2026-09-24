"use client";

import { useMemo, useState } from "react";

import type { AgentSessionListItem } from "@/lib/api/agent";

type Props = {
  open: boolean;
  sessions: AgentSessionListItem[];
  activeId: string | null;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
};

function formatSessionTitle(session: AgentSessionListItem): string {
  const date = new Date(session.updated_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  const hint = session.skill_hint?.replace("resume-", "") ?? session.kind;
  return `${hint} · ${date}`;
}

export function AgentHistoryDrawer({ open, sessions, activeId, onClose, onSelect, onNew }: Props) {
  const sorted = useMemo(
    () => [...sessions].sort((a, b) => b.updated_at.localeCompare(a.updated_at)),
    [sessions],
  );

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-40 flex">
      <button type="button" className="flex-1 bg-black/20" onClick={onClose} aria-label="关闭历史" />
      <aside className="flex h-full w-[min(18rem,88vw)] flex-col border-l border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2.5">
          <p className="text-sm font-semibold text-slate-900">历史会话</p>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onNew}
              className="rounded-lg px-2 py-1 text-[11px] font-medium text-brand-700 hover:bg-brand-50"
            >
              新对话
            </button>
            <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-100">
              ×
            </button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2">
          {sorted.length === 0 ? (
            <p className="px-2 py-8 text-center text-xs text-slate-400">暂无历史会话</p>
          ) : (
            <ul className="space-y-1">
              {sorted.map((session) => {
                const active = session.id === activeId;
                return (
                  <li key={session.id}>
                    <button
                      type="button"
                      onClick={() => {
                        onSelect(session.id);
                        onClose();
                      }}
                      className={`w-full rounded-xl px-3 py-2.5 text-left transition ${
                        active
                          ? "bg-slate-900 text-white"
                          : "hover:bg-slate-50 text-slate-700"
                      }`}
                    >
                      <p className="text-[12px] font-medium">{formatSessionTitle(session)}</p>
                      <p className={`mt-0.5 truncate font-mono text-[10px] ${active ? "text-white/70" : "text-slate-400"}`}>
                        {session.id}
                      </p>
                    </button>
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
