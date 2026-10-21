import type { AgentUiContext } from "@/lib/ui-context";

export type AgentAttachment = {
  kind: "image" | "file" | "audio";
  name: string;
  label?: string | null;
  mime_type?: string | null;
  /** Present while the message is being composed and on the live turn only. */
  data_url?: string | null;
  text_preview?: string | null;
  /** Object-storage key. Set on replayed history, where the bytes are not inline. */
  storage_key?: string | null;
  /** Signed URL re-issued by the server on every read; short-lived. */
  download_url?: string | null;
  size_bytes?: number | null;
  /**
   * Audio only. Browser speech-to-text; there is no server-side STT in this version,
   * so these words are the only readable form of the clip and the only thing the model
   * sees. Sent alongside the recording and stored on the same row.
   */
  transcript?: string | null;
  duration_ms?: number | null;
  /** Set by the server when the clip could not be archived to object storage. */
  storage_error?: boolean | null;
};

/** Human-readable clip length, for the voice bubble. */
export function formatClipDuration(ms?: number | null): string | null {
  if (!ms || ms < 1000) return null;
  const total = Math.round(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return minutes > 0 ? `${minutes}分${String(seconds).padStart(2, "0")}秒` : `${seconds}秒`;
}

/** Where the bytes live for this attachment: inline while composing, signed after. */
export function attachmentSrc(att: AgentAttachment): string | null {
  return att.data_url ?? att.download_url ?? null;
}

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
  /**
   * The run is waiting for the single harness slot. Transient and not persisted: it
   * describes this moment, not the turn. Without it a queued run looks identical to a
   * hung one — the server is silent either way.
   */
  | { type: "queued"; waited_sec?: number; ahead?: number }
  | { type: "done" }
  /**
   * Transport-level keep-alive (`jc/api/sse.py`). `coach`/`writer` can legitimately
   * run for minutes across a failover chain; a ping is how the client tells "still
   * connected, still working" apart from "nothing is coming back". Never persisted.
   */
  | { type: "ping" }
  | {
      type: "confirm";
      confirm_id?: string;
      profile_id?: string;
      patch?: Record<string, unknown>;
      preview?: Record<string, unknown>;
    };

export type AgentDisplayItem =
  | {
      id: string;
      kind: "user";
      content: string;
      attachments?: AgentAttachment[];
      /** Set when the turn this message started never produced a reply. Drives the
       * retry affordance on the bubble; cleared once a retry is sent. */
      failed?: boolean;
    }
  | { id: string; kind: "assistant"; content: string; streaming?: boolean; reveal?: boolean }
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
      status: "pending" | "applied" | "rejected" | "superseded";
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

/** Live wait while the run sits behind other users' runs. */
export type AgentQueueWait = {
  waitedSec: number;
  /** Runs ahead of this one. 0 means it is next. */
  ahead: number;
};

export type QueuedAgentMessage = {
  id: string;
  content: string;
  attachments: AgentAttachment[];
  mode: "follow_up" | "steer";
  uiContext?: AgentUiContext | null;
};
