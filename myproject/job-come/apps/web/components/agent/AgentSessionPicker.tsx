"use client";

import type { AgentSessionListItem } from "@/lib/api/agent";

type Props = {
  sessions: AgentSessionListItem[];
  activeId: string | null;
  onSelect: (sessionId: string) => void;
  onNew: () => void;
};

export function AgentSessionPicker({ sessions, activeId, onSelect, onNew }: Props) {
  if (sessions.length === 0) {
    return (
      <button
        type="button"
        onClick={onNew}
        className="text-[10px] text-neutral-500 underline"
      >
        新会话
      </button>
    );
  }

  return (
    <div className="flex max-w-[220px] items-center gap-1">
      <select
        className="max-w-full truncate rounded border border-neutral-200 bg-white px-1.5 py-0.5 text-[10px] text-neutral-700"
        value={activeId ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          if (v) onSelect(v);
        }}
      >
        <option value="" disabled>历史会话</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {s.skill_hint ?? s.kind} · {new Date(s.updated_at).toLocaleDateString()}
          </option>
        ))}
      </select>
      <button type="button" onClick={onNew} className="shrink-0 text-[10px] text-neutral-500 underline">
        新建
      </button>
    </div>
  );
}
