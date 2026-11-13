import type { AgentUiDisplayItem } from "./display-items";

export type ToolActivity = {
  id: string;
  name: string;
  args?: unknown;
  result?: string;
  state: "running" | "done" | "error";
};

import { MOCK_ASK_TOOL, mockQuestionLabel } from "@/lib/agent/mock-question-label";

export type TurnActivity =
  | { kind: "skill"; id: string; name: string }
  | { kind: "mock_question"; id: string; label: string }
  | { kind: "thinking"; id: string; content: string }
  | { kind: "tool"; tool: ToolActivity }
  | { kind: "plan"; id: string; todos: Array<Record<string, unknown>> }
  | { kind: "subagent"; id: string; name: string; description?: string; state: "running" | "done" }
  | { kind: "error"; id: string; message: string }
  | { kind: "confirm"; item: Extract<AgentUiDisplayItem, { kind: "confirm" }> };

export type AgentTurn = {
  id: string;
  user?: Extract<AgentUiDisplayItem, { kind: "user" }>;
  assistant?: Extract<AgentUiDisplayItem, { kind: "assistant" }>;
  activities: TurnActivity[];
  streaming: boolean;
};

function finalizeTools(activities: TurnActivity[]): TurnActivity[] {
  return activities.map((activity) => {
    if (activity.kind !== "tool" || activity.tool.state !== "running") return activity;
    return {
      ...activity,
      tool: { ...activity.tool, state: "done" },
    };
  });
}

function pushActivity(activities: TurnActivity[], item: AgentUiDisplayItem): TurnActivity[] {
  const next = [...activities];
  if (item.kind === "skill") {
    next.push({ kind: "skill", id: item.id, name: item.name });
    return next;
  }
  // A question the interviewer put in a mock interview shows as a numbered marker, not as a tool
  // call: the candidate sees "第 3 题", not the tool's name and JSON.
  if (item.kind === "tool_start" && item.name === MOCK_ASK_TOOL) return next;
  if (item.kind === "tool_result" && item.name === MOCK_ASK_TOOL) {
    const label = mockQuestionLabel(item.result);
    if (label) next.push({ kind: "mock_question", id: item.id, label });
    return next;
  }
  if (item.kind === "thinking") {
    next.push({ kind: "thinking", id: item.id, content: item.content });
    return next;
  }
  if (item.kind === "tool_start") {
    if (item.name === "write_todos") {
      const args = item.args as { todos?: Array<Record<string, unknown>>; items?: Array<Record<string, unknown>> } | undefined;
      const todos = args?.todos ?? args?.items;
      if (todos?.length) {
        next.push({ kind: "plan", id: item.id, todos });
      }
      return next;
    }
    if (item.name === "task") {
      const args = item.args as { description?: string; prompt?: string; subagent_type?: string; agent?: string } | undefined;
      next.push({
        kind: "subagent",
        id: item.id,
        name: args?.subagent_type || args?.agent || "subagent",
        description: args?.description || args?.prompt,
        state: "running",
      });
      return next;
    }
    next.push({
      kind: "tool",
      tool: { id: item.id, name: item.name || "tool", args: item.args, state: "running" },
    });
    return next;
  }
  if (item.kind === "plan_todos") {
    next.push({ kind: "plan", id: item.id, todos: item.todos });
    return next;
  }
  if (item.kind === "subagent") {
    const existing = next.findIndex((a) => a.kind === "subagent" && a.name === item.name && a.state === "running");
    if (existing >= 0 && next[existing].kind === "subagent") {
      next[existing] = { ...next[existing], state: item.state };
      return next;
    }
    next.push({
      kind: "subagent",
      id: item.id,
      name: item.name,
      description: item.description,
      state: item.state,
    });
    return next;
  }
  if (item.kind === "tool_result") {
    const name = item.name || "tool";
    const idx = next.findIndex((a) => a.kind === "tool" && a.tool.state === "running" && a.tool.name === name);
    const fallback = next.findIndex((a) => a.kind === "tool" && a.tool.state === "running");
    const target = idx >= 0 ? idx : fallback;
    if (target >= 0 && next[target].kind === "tool") {
      const tool = next[target].tool;
      next[target] = {
        kind: "tool",
        tool: {
          ...tool,
          result: item.result,
          state: item.result.toLowerCase().includes("error") ? "error" : "done",
        },
      };
      return next;
    }
    next.push({ kind: "tool", tool: { id: item.id, name, result: item.result, state: "done" } });
    return next;
  }
  if (item.kind === "error") {
    next.push({ kind: "error", id: item.id, message: item.message });
    return next;
  }
  if (item.kind === "confirm") {
    next.push({ kind: "confirm", item });
  }
  return next;
}

export function buildAgentTurns(items: AgentUiDisplayItem[], busy: boolean): AgentTurn[] {
  const turns: AgentTurn[] = [];
  let current: AgentTurn | null = null;
  let turnIdx = 0;

  function ensureTurn(): AgentTurn {
    if (!current) {
      current = { id: `turn_${turnIdx++}`, activities: [], streaming: false };
      turns.push(current);
    }
    return current;
  }

  for (const item of items) {
    if (item.kind === "usage") continue;

    if (item.kind === "user") {
      current = { id: `turn_${turnIdx++}`, user: item, activities: [], streaming: false };
      turns.push(current);
      continue;
    }

    const turn = ensureTurn();

    if (item.kind === "assistant") {
      turn.assistant = item;
      turn.streaming = Boolean(item.streaming);
      continue;
    }

    turn.activities = pushActivity(turn.activities, item);
  }

  const last = turns[turns.length - 1];
  if (last) {
    // `turn.streaming` so far only reflects the assistant item's own flag, which does
    // not exist yet during the gap between "user sent" and "first token". That gap is
    // long — measured 10-16 s on a warm session, because the harness assembles its
    // prompt and makes a first model call before any token arrives. Without a streaming
    // turn the thread renders as a finished turn with no indicator: the user sees their
    // own message and then nothing, which reads as "it broke".
    //
    // `busy` (the session's own request-in-flight flag) is the only signal covering
    // this gap. The earlier form of this rule also required `activities.length === 0`,
    // and that made the indicator vanish about 0.6 s in: the harness emits a `skill`
    // event almost immediately, which is an activity but not progress the user waits
    // on. So the test is "no answer text yet", not "nothing has arrived yet". An
    // `error` activity ends the wait honestly — that turn did produce an outcome.
    if (busy && !last.assistant?.content && !last.activities.some((a) => a.kind === "error")) {
      last.streaming = true;
    }
    if (!last.streaming) {
      last.activities = finalizeTools(last.activities);
    }
  }

  return turns;
}
