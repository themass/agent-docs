"use client";

import { useState } from "react";

import type { QueuedAgentMessage } from "@/lib/types/agent";

type Props = {
  followUp: QueuedAgentMessage[];
  steerCount: number;
  busy: boolean;
  onRemove: (id: string) => void;
  onClearSteer: () => void;
};

export function AgentTaskQueue({ followUp, steerCount, busy, onRemove, onClearSteer }: Props) {
  const [open, setOpen] = useState(true);
  if (!busy && followUp.length === 0 && steerCount === 0) return null;

  return (
    <div className="shrink-0 border-t border-surface-border bg-surface/80 px-2.5 py-2 backdrop-blur">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left text-xs text-ink-600"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-semibold text-ink-800">任务队列</span>
        <span className="badge badge-neutral tabular-nums">
          {followUp.length + steerCount}
        </span>
        <span className="min-w-0 flex-1 truncate text-ink-500">
          {busy ? "运行中 · Enter 排队 · Ctrl+Enter 插队" : "等待发送"}
        </span>
        <span className="text-ink-500">{open ? "▾" : "▸"}</span>
      </button>

      {open ? (
        <div className="mt-2 space-y-2">
          {steerCount > 0 ? (
            <div className="rounded-lg bg-warn-50 px-2.5 py-2 text-xs ring-1 ring-inset ring-warn-100">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-warn-900">插队纠偏 ×{steerCount}</span>
                <button type="button" className="font-medium text-warn-700 hover:text-warn-900" onClick={onClearSteer}>
                  清空
                </button>
              </div>
              <p className="mt-1 text-warn-700">下一条模型轮次将优先处理插队内容</p>
            </div>
          ) : null}

          {followUp.length > 0 ? (
            <ul className="space-y-1.5">
              {followUp.map((task, idx) => (
                <li
                  key={task.id}
                  className="flex items-start gap-2 rounded-lg bg-surface-sunken px-2.5 py-2 text-xs ring-1 ring-inset ring-surface-border"
                >
                  <span className="mt-0.5 font-mono text-ink-500">{idx + 1}</span>
                  <span className="min-w-0 flex-1 whitespace-pre-wrap text-ink-700">{task.content}</span>
                  <button
                    type="button"
                    className="shrink-0 text-ink-400 hover:text-danger-600"
                    onClick={() => onRemove(task.id)}
                    aria-label="移除"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
