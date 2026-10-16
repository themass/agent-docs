"use client";

import {
  AuiIf,
  MessagePrimitive,
  ThreadPrimitive,
  type TextMessagePartComponent,
} from "@assistant-ui/react";
import { useEffect, useRef } from "react";

import { AgentMark } from "@/components/agent/AgentMark";
import { AgentMarkdownText } from "@/components/agent/assistant-ui/AgentMarkdownText";
import {
  AgentThreadUIContext,
  type AgentThreadUIHandlers,
} from "@/components/agent/assistant-ui/AgentThreadUIContext";
import {
  JCConfirmTool,
  JCSubagentTool,
  JCToolFallback,
} from "@/components/agent/assistant-ui/JCToolParts";
import { ZHOUKA_NAME } from "@/lib/brand";
import type { AgentDisplayItem } from "@/lib/types/agent";

const UserTextPart: TextMessagePartComponent = ({ text }) => (
  <p className="whitespace-pre-wrap text-sm leading-relaxed">{text}</p>
);

function UserMessage() {
  return (
    <MessagePrimitive.Root className="flex justify-end">
      <div className="max-w-[88%] rounded-xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-white shadow-xs">
        <MessagePrimitive.Parts components={{ Text: UserTextPart }} />
      </div>
    </MessagePrimitive.Root>
  );
}

function AssistantMessage() {
  return (
    <MessagePrimitive.Root className="flex items-start gap-2">
      <AgentMark size={24} className="mt-0.5 shrink-0" />
      <div className="min-w-0 max-w-[calc(100%-2rem)] flex-1 space-y-2">
        <MessagePrimitive.Parts
          components={{
            Text: AgentMarkdownText,
            tools: {
              by_name: {
                jc_confirm: JCConfirmTool,
                task: JCSubagentTool,
              },
              Fallback: JCToolFallback,
            },
          }}
        />
        <AuiIf condition={(s) => s.message.status?.type === "running"}>
          <span className="inline-block h-3.5 w-0.5 animate-pulse bg-brand-500 align-middle" />
        </AuiIf>
      </div>
    </MessagePrimitive.Root>
  );
}

type Props = {
  items: AgentDisplayItem[];
  busy?: boolean;
  variant?: "default" | "sidebar";
  handlers: AgentThreadUIHandlers;
};

export function AgentAssistantThread({
  items,
  busy = false,
  variant = "default",
  handlers,
}: Props) {
  const isSidebar = variant === "sidebar";
  const bottomRef = useRef<HTMLDivElement>(null);
  const isEmpty = items.length === 0;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [items, busy]);

  return (
    <AgentThreadUIContext.Provider value={handlers}>
      <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
        <ThreadPrimitive.Viewport
          className={`min-h-0 flex-1 overflow-y-auto overflow-x-hidden ${
            isSidebar ? "px-2.5 py-2" : "px-3 py-3"
          }`}
        >
          {isEmpty ? (
            <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
              <AgentMark size={40} className="mb-3" />
              <p className="text-sm font-medium text-ink-700">{ZHOUKA_NAME}</p>
              <p className="mt-1.5 max-w-[240px] text-xs leading-relaxed text-ink-500">
                描述要优化的经历、粘贴 JD 或截图
              </p>
            </div>
          ) : (
            <div className={isSidebar ? "space-y-3" : "space-y-4"}>
              <ThreadPrimitive.Messages
                components={{
                  UserMessage,
                  AssistantMessage,
                }}
              />
            </div>
          )}

          {busy && items.length > 0 ? (
            <div className="mt-2 inline-flex animate-fade-in items-center gap-2 rounded-full bg-brand-50 px-3 py-1.5 text-xs font-medium text-brand-700 ring-1 ring-inset ring-brand-100">
              <span className="size-1.5 animate-pulse rounded-full bg-brand-500" />
              等待模型响应…
            </div>
          ) : null}

          <div ref={bottomRef} />
        </ThreadPrimitive.Viewport>
      </ThreadPrimitive.Root>
    </AgentThreadUIContext.Provider>
  );
}
