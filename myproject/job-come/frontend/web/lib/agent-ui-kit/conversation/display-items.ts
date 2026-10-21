/** Protocol-agnostic stream items for the conversation thread (host maps server events → these). */

export type AgentUiAttachment = {
  kind: "image" | "file" | "audio";
  name: string;
  label?: string | null;
  mime_type?: string | null;
  data_url?: string | null;
  text_preview?: string | null;
  storage_key?: string | null;
  download_url?: string | null;
  size_bytes?: number | null;
  transcript?: string | null;
  duration_ms?: number | null;
  storage_error?: boolean | null;
};

export function attachmentSrc(att: AgentUiAttachment): string | null {
  return att.data_url ?? att.download_url ?? null;
}

export type AgentUiDisplayItem =
  | {
      id: string;
      kind: "user";
      content: string;
      attachments?: AgentUiAttachment[];
      /** This message's turn ended without a reply. Drives the retry affordance. */
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
