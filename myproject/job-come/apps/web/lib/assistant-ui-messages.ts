/** Map JobCome turns → assistant-ui thread messages (text + tool-call parts). */

import type { ThreadAssistantMessagePart, ThreadMessageLike } from "@assistant-ui/react";

import { buildAgentTurns } from "@/lib/agent-turn-model";
import type { AgentDisplayItem } from "@/lib/types/agent";
import type { TurnActivity } from "@/lib/agent-turn-model";

type JsonArgs = Record<string, string | number | boolean | null>;

function jsonArgs(value: unknown): JsonArgs {
  if (!value || typeof value !== "object") return {};
  try {
    return JSON.parse(JSON.stringify(value)) as JsonArgs;
  } catch {
    return {};
  }
}

function activityToParts(activity: TurnActivity): ThreadAssistantMessagePart[] {
  if (activity.kind === "skill") {
    return [
      {
        type: "tool-call",
        toolCallId: activity.id,
        toolName: "jobcome_skill",
        args: { name: activity.name },
        argsText: JSON.stringify({ name: activity.name }),
        result: { status: "done" },
      },
    ];
  }
  if (activity.kind === "thinking") {
    return [
      {
        type: "tool-call",
        toolCallId: activity.id,
        toolName: "jobcome_thinking",
        args: { preview: activity.content.slice(0, 120) },
        argsText: JSON.stringify({ preview: activity.content.slice(0, 120) }),
        result: { content: activity.content },
      },
    ];
  }
  if (activity.kind === "plan") {
    return [
      {
        type: "tool-call",
        toolCallId: activity.id,
        toolName: "write_todos",
        args: { todos: activity.todos as unknown as JsonArgs },
        argsText: JSON.stringify({ todos: activity.todos }),
        result: { status: "done" },
      },
    ];
  }
  if (activity.kind === "subagent") {
    const running = activity.state === "running";
    return [
      {
        type: "tool-call",
        toolCallId: activity.id,
        toolName: "task",
        args: {
          subagent_type: activity.name,
          description: activity.description ?? "",
        },
        argsText: JSON.stringify({
          subagent_type: activity.name,
          description: activity.description,
        }),
        ...(running ? {} : { result: { status: activity.state } }),
      },
    ];
  }
  if (activity.kind === "tool") {
    const { tool } = activity;
    const running = tool.state === "running";
    return [
      {
        type: "tool-call",
        toolCallId: tool.id,
        toolName: tool.name,
        args: jsonArgs(tool.args),
        argsText: JSON.stringify(tool.args ?? {}, null, 2),
        ...(running ? {} : { result: tool.result ?? { status: tool.state } }),
      },
    ];
  }
  if (activity.kind === "confirm") {
    const item = activity.item;
    return [
      {
        type: "tool-call",
        toolCallId: item.id,
        toolName: "jobcome_confirm",
        args: {
          confirm_id: item.confirmId,
          profile_id: item.profileId ?? "",
          status: item.status,
        },
        argsText: JSON.stringify({
          confirm_id: item.confirmId,
          patch: item.patch,
          preview: item.preview,
        }),
        result: item.status !== "pending" ? { status: item.status } : undefined,
      },
    ];
  }
  if (activity.kind === "error") {
    return [
      {
        type: "tool-call",
        toolCallId: activity.id,
        toolName: "jobcome_error",
        args: { message: activity.message },
        argsText: JSON.stringify({ message: activity.message }),
        result: { status: "error" },
      },
    ];
  }
  return [];
}

export function displayItemsToThreadMessages(
  items: AgentDisplayItem[],
  busy: boolean,
): ThreadMessageLike[] {
  const turns = buildAgentTurns(items, busy);
  const messages: ThreadMessageLike[] = [];

  for (const turn of turns) {
    if (turn.user) {
      messages.push({
        id: turn.user.id,
        role: "user",
        content: [{ type: "text", text: turn.user.content }],
      });
    }

    const parts: ThreadAssistantMessagePart[] = [];
    for (const activity of turn.activities) {
      parts.push(...activityToParts(activity));
    }
    if (turn.assistant?.content) {
      parts.push({ type: "text", text: turn.assistant.content });
    }

    if (parts.length > 0 || turn.streaming) {
      messages.push({
        id: turn.assistant?.id ?? turn.id,
        role: "assistant",
        content: parts.length > 0 ? parts : [{ type: "text", text: "" }],
        status: turn.streaming
          ? { type: "running" }
          : { type: "complete", reason: "stop" },
      });
    }
  }

  const last = messages[messages.length - 1];
  if (busy && (!last || last.role === "user")) {
    messages.push({
      id: `streaming_${Date.now()}`,
      role: "assistant",
      content: [{ type: "text", text: "" }],
      status: { type: "running" },
    });
  }

  return messages;
}
