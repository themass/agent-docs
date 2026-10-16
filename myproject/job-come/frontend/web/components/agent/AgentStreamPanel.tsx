"use client";

import { useEffect, useRef } from "react";

import { AgentLoopCard } from "@/components/agent/AgentLoopCard";
import { AgentMark } from "@/components/agent/AgentMark";
import { buildAgentTurns } from "@/lib/agent-turn-model";
import { ZHOUKA_NAME } from "@/lib/brand";
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
              <p className="text-sm font-medium text-ink-700">{ZHOUKA_NAME}</p>
              <p className="mt-1.5 max-w-[240px] text-xs leading-relaxed text-ink-500">
                描述要优化的经历、粘贴 JD 或截图
              </p>
            </div>
          ) : (
            turns.map((turn) => <AgentLoopCard key={turn.id} turn={turn} onConfirm={onConfirm} />)
          )}

          {busy && !turns.some((t) => t.streaming) && turns.length > 0 ? (
            <div className="inline-flex animate-fade-in items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-100">
              <span className="size-1.5 animate-pulse rounded-full bg-brand-500" />
              等待模型响应…
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}
