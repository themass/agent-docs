export type AgentAttachment = {
  kind: "image" | "file" | "audio";
  name: string;
  label?: string | null;
  mime_type?: string | null;
  data_url?: string | null;
  text_preview?: string | null;
};

export type AgentSession = {
  id: string;
  deerflow_thread_id: string;
  skill_hint: string | null;
  kind: string;
  status: string;
  profile_id: string | null;
  created_at: string;
};

export type AgentMessageRecord = {
  id: string;
  session_id: string;
  role: string;
  event_type: string;
  content: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type AgentStreamEvent =
  | { type: "token"; content?: string }
  | { type: "skill"; name?: string }
  | { type: "thinking"; content?: string }
  | { type: "tool_start"; name?: string; args?: unknown }
  | { type: "tool_result"; name?: string; result?: string }
  | { type: "plan_todos"; todos?: Array<Record<string, unknown>> }
  | { type: "subagent_start"; name?: string; description?: string }
  | { type: "subagent_done"; name?: string; result?: string }
  | { type: "tool"; name?: string; args?: unknown; result?: string }
  | { type: "usage"; prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }
  | {
      type: "context_usage";
      used_tokens?: number;
      limit_tokens?: number;
      percent?: number;
      estimated?: boolean;
      buckets?: AgentContextBucket[];
      actual?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
    }
  | { type: "error"; message?: string }
  | { type: "done" }
  | {
      type: "confirm";
      confirm_id?: string;
      profile_id?: string;
      patch?: Record<string, unknown>;
      preview?: Record<string, unknown>;
    };

export type AgentDisplayItem =
  | { id: string; kind: "user"; content: string; attachments?: AgentAttachment[] }
  | { id: string; kind: "assistant"; content: string; streaming?: boolean }
  | { id: string; kind: "skill"; name: string }
  | { id: string; kind: "thinking"; content: string }
  | { id: string; kind: "tool_start"; name: string; args?: unknown }
  | { id: string; kind: "tool_result"; name: string; result: string }
  | { id: string; kind: "plan_todos"; todos: Array<Record<string, unknown>> }
  | { id: string; kind: "subagent"; name: string; description?: string; state: "running" | "done" }
  | { id: string; kind: "usage"; prompt: number; completion: number; total: number }
  | { id: string; kind: "error"; message: string }
  | {
      id: string;
      kind: "confirm";
      confirmId: string;
      profileId?: string;
      patch?: Record<string, unknown>;
      preview?: Record<string, unknown>;
      status: "pending" | "applied" | "rejected";
    };

export type TokenUsageTotals = {
  prompt: number;
  completion: number;
  total: number;
  turns: number;
};

export type AgentContextBucket = {
  id: string;
  label: string;
  tokens: number;
};

export type AgentContextUsage = {
  used_tokens: number;
  limit_tokens: number;
  percent: number;
  estimated: boolean;
  buckets: AgentContextBucket[];
  turns: number;
  actual?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
};

export type QueuedAgentMessage = {
  id: string;
  content: string;
  attachments: AgentAttachment[];
  mode: "follow_up" | "steer";
  uiContext?: AgentUiContext | null;
};
