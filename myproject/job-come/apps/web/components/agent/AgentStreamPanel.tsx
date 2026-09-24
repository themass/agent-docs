"use client";

import { useEffect, useRef } from "react";

import { AgentLoopCard } from "@/components/agent/AgentLoopCard";
import { AgentMark } from "@/components/agent/AgentMark";
import { buildAgentTurns } from "@/lib/agent-turn-model";
import type { AgentDisplayItem } from "@/lib/types/agent";

export function AgentStreamPanel({
  items,
  onConfirm,
  variant = "default",
  busy = false,
}: {
  items: AgentDisplayItem[];
  onConfirm?: (confirmId: string, approved: boolean) => void;
  variant?: "default" | "sidebar";
  busy?: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const isSidebar = variant === "sidebar";
  const turns = buildAgentTurns(items, busy);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items, busy]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className={`min-h-0 flex-1 overflow-y-auto overflow-x-hidden ${isSidebar ? "px-2.5 py-2" : "px-3 py-3"}`}>
        <div className={isSidebar ? "space-y-3" : "space-y-4"}>
          {turns.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
              <AgentMark size={40} className="mb-3" />
              <p className="text-[13px] font-medium text-slate-700">JobCome Agent</p>
              <p className="mt-1 max-w-[220px] text-[11px] leading-relaxed text-slate-400">
                描述要优化的经历、粘贴 JD 或截图
              </p>
            </div>
          ) : (
            turns.map((turn) => <AgentLoopCard key={turn.id} turn={turn} onConfirm={onConfirm} />)
          )}

          {busy && !turns.some((t) => t.streaming) && turns.length > 0 ? (
            <div className="rounded-2xl border border-sky-200 bg-white px-3 py-2 text-[11px] text-sky-700">
              <span className="inline-flex items-center gap-2">
                <span className="size-2 animate-pulse rounded-full bg-sky-500" />
                等待模型响应…
              </span>
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
