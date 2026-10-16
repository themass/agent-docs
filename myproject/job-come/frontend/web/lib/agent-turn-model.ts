import type { AgentDisplayItem } from "@/lib/types/agent";

export type ToolActivity = {
  id: string;
  name: string;
  args?: unknown;
  result?: string;
  state: "running" | "done" | "error";
};

export type TurnActivity =
  | { kind: "skill"; id: string; name: string }
  | { kind: "thinking"; id: string; content: string }
  | { kind: "tool"; tool: ToolActivity }
  | { kind: "plan"; id: string; todos: Array<Record<string, unknown>> }
  | { kind: "subagent"; id: string; name: string; description?: string; state: "running" | "done" }
  | { kind: "error"; id: string; message: string }
  | { kind: "confirm"; item: Extract<AgentDisplayItem, { kind: "confirm" }> };

export type AgentTurn = {
  id: string;
  user?: Extract<AgentDisplayItem, { kind: "user" }>;
  assistant?: Extract<AgentDisplayItem, { kind: "assistant" }>;
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

function pushActivity(activities: TurnActivity[], item: AgentDisplayItem): TurnActivity[] {
  const next = [...activities];
  if (item.kind === "skill") {
    next.push({ kind: "skill", id: item.id, name: item.name });
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

export function buildAgentTurns(items: AgentDisplayItem[], busy: boolean): AgentTurn[] {
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
  if (last && !last.streaming && !busy) {
    last.activities = finalizeTools(last.activities);
  } else if (last && busy && !last.streaming) {
    last.activities = finalizeTools(last.activities);
  }

  return turns;
}
