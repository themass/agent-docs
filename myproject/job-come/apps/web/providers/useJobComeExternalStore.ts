"use client";

import type { AppendMessage, ThreadMessageLike } from "@assistant-ui/react";
import { useCallback, useMemo } from "react";

import { displayItemsToThreadMessages } from "@/lib/assistant-ui-messages";
import type { AgentAttachment, AgentDisplayItem } from "@/lib/types/agent";

export type JobComeAgentSurface = {
  items: AgentDisplayItem[];
  busy: boolean;
  sendMessage: (
    content: string,
    attachments: AgentAttachment[],
    mode?: "send" | "follow_up" | "steer",
  ) => void | Promise<void>;
  stopRun?: () => void;
};

function appendMessageText(message: AppendMessage): string {
  return message.content
    .map((part) => (part.type === "text" ? part.text : ""))
    .join("")
    .trim();
}

/** External store adapter backing assistant-ui runtime (OpenHuman pattern). */
export function useJobComeExternalStore(agent: JobComeAgentSurface) {
  const runtimeMessages = useMemo(
    () => displayItemsToThreadMessages(agent.items, agent.busy),
    [agent.items, agent.busy],
  );

  const onNew = useCallback(
    async (message: AppendMessage) => {
      const text = appendMessageText(message);
      if (!text) return;
      await agent.sendMessage(text, []);
    },
    [agent.sendMessage],
  );

  const onCancel = useCallback(async () => {
    agent.stopRun?.();
  }, [agent.stopRun]);

  return useMemo(
    () => ({
      messages: runtimeMessages,
      isRunning: agent.busy,
      isLoading: false,
      convertMessage: (m: ThreadMessageLike) => m,
      onNew,
      onCancel,
    }),
    [runtimeMessages, agent.busy, onNew, onCancel],
  );
}
