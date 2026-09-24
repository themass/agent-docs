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
    <div className="shrink-0 border-t border-slate-200/60 bg-white/80 px-2.5 py-2">
      <button
        type="button"
        className="flex w-full items-center gap-2 text-left text-[11px] text-slate-600"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-semibold text-slate-800">任务队列</span>
        <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600">
          {followUp.length + steerCount}
        </span>
        <span className="min-w-0 flex-1 truncate text-slate-400">
          {busy ? "运行中 · Enter 排队 · Ctrl+Enter 插队" : "等待发送"}
        </span>
        <span className="text-slate-400">{open ? "▾" : "▸"}</span>
      </button>

      {open ? (
        <div className="mt-2 space-y-2">
          {steerCount > 0 ? (
            <div className="rounded-xl border border-amber-200 bg-amber-50/60 px-2.5 py-2 text-[11px]">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-amber-900">插队纠偏 ×{steerCount}</span>
                <button type="button" className="text-amber-700 hover:underline" onClick={onClearSteer}>
                  清空
                </button>
              </div>
              <p className="mt-1 text-amber-800/80">下一条模型轮次将优先处理插队内容</p>
            </div>
          ) : null}

          {followUp.length > 0 ? (
            <ul className="space-y-1.5">
              {followUp.map((task, idx) => (
                <li
                  key={task.id}
                  className="flex items-start gap-2 rounded-xl border border-slate-200 bg-slate-50 px-2.5 py-2 text-[11px]"
                >
                  <span className="mt-0.5 font-mono text-slate-400">{idx + 1}</span>
                  <span className="min-w-0 flex-1 whitespace-pre-wrap text-slate-700">{task.content}</span>
                  <button
                    type="button"
                    className="shrink-0 text-slate-400 hover:text-red-600"
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
