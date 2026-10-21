"use client";

import { sessionListTitle } from "@/lib/agent-session-display";
import type { AgentSessionListItem } from "@/lib/api/agent";
import { Select } from "@/components/ui/Select";

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
        className="btn btn-sm btn-ghost text-micro"
      >
        新会话
      </button>
    );
  }

  return (
    <div className="flex max-w-[220px] items-center gap-1">
      <Select
        className="max-w-full"
        selectClassName="truncate px-1.5 py-0.5 text-micro"
        value={activeId ?? ""}
        onChange={(e) => {
          const v = e.target.value;
          if (v) onSelect(v);
        }}
      >
        <option value="" disabled>历史会话</option>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>
            {sessionListTitle(s)}
          </option>
        ))}
      </Select>
      <button type="button" onClick={onNew} className="btn btn-sm btn-ghost shrink-0 text-micro">
        新建
      </button>
    </div>
  );
}
