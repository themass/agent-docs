"use client";

import { useEffect, useRef } from "react";

import { AgentThinkingIndicator } from "../AgentThinkingIndicator";
import { AgentTurnCard } from "./AgentTurnCard";
import type { AgentUiDisplayItem } from "./display-items";
import type { AgentConversationChrome, AgentConversationThreadLabels } from "./types";
import { buildAgentTurns } from "./turn-model";

export type AgentConversationThreadProps = {
  items: AgentUiDisplayItem[];
  busy?: boolean;
  variant?: "default" | "sidebar";
  labels: AgentConversationThreadLabels;
  chrome: AgentConversationChrome;
  onConfirm?: (confirmId: string, approved: boolean) => void;
  confirmingId?: string | null;
  onRetry?: (itemId: string) => void;
};

export function AgentConversationThread({
  items,
  busy = false,
  variant = "default",
  labels,
  chrome,
  onConfirm,
  confirmingId = null,
  onRetry,
}: AgentConversationThreadProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const followRef = useRef(true);
  const isSidebar = variant === "sidebar";
  const turns = buildAgentTurns(items, busy);

  useEffect(() => {
    const scroller = scrollRef.current;
    const content = contentRef.current;
    if (!scroller || !content) return;
    // Progressive text grows without a new SSE item. Observe the actual content,
    // and do not pull the user down if they scrolled up to read an earlier reply.
    const observer = new ResizeObserver(() => {
      if (followRef.current) scroller.scrollTop = scroller.scrollHeight;
    });
    observer.observe(content);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    followRef.current = true;
    const scroller = scrollRef.current;
    if (scroller) scroller.scrollTop = scroller.scrollHeight;
  }, [turns.length]);

  const emptyIcon = chrome.renderAgentIcon({ size: 40, className: "mb-3" });
  const thinkingPill = (
    <AgentThinkingIndicator
      label={labels.thinkingLabel}
      avatar={chrome.renderAgentIcon({ size: 20, thinking: true })}
    />
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scrollRef}
        onScroll={() => {
          const el = scrollRef.current;
          if (el) followRef.current = el.scrollHeight - el.clientHeight - el.scrollTop < 72;
        }}
        className={`min-h-0 flex-1 overflow-y-auto overflow-x-hidden ${isSidebar ? "px-2.5 py-2" : "px-3 py-3"}`}
      >
        <div ref={contentRef} className={isSidebar ? "space-y-3" : "space-y-4"}>
          {turns.length === 0 ? (
            busy ? (
              thinkingPill
            ) : (
              <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
                {emptyIcon}
                <p className="text-sm font-medium text-ink-700">{labels.emptyTitle}</p>
                <p className="mt-1.5 max-w-[240px] text-xs leading-relaxed text-ink-500">{labels.emptyHint}</p>
              </div>
            )
          ) : (
            turns.map((turn) => (
              <AgentTurnCard
                key={turn.id}
                turn={turn}
                labels={labels}
                chrome={chrome}
                onConfirm={onConfirm}
                confirmingId={confirmingId}
                onRetry={onRetry}
              />
            ))
          )}

          {busy && !turns.some((t) => t.streaming) && turns.length > 0 ? thinkingPill : null}

        </div>
      </div>
    </div>
  );
}
