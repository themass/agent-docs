import type {
  AgentAttachment,
  AgentMessageRecord,
  AgentSession,
  AgentStreamEvent,
} from "@/lib/types/agent";
import { apiJson, API_BASE } from "./client";

export function createAgentSession(body: {
  profile_id?: string | null;
  job_id?: string | null;
  skill_hint?: string;
  kind?: string;
}): Promise<AgentSession> {
  return apiJson<AgentSession>("/agent/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type AgentSessionListItem = {
  id: string;
  skill_hint: string | null;
  kind: string;
  status: string;
  profile_id: string | null;
  created_at: string;
  updated_at: string;
};

export function listAgentSessions(params?: {
  profile_id?: string | null;
  kind?: string;
  limit?: number;
}): Promise<{ sessions: AgentSessionListItem[] }> {
  const q = new URLSearchParams();
  if (params?.profile_id) q.set("profile_id", params.profile_id);
  if (params?.kind) q.set("kind", params.kind);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiJson(`/agent/sessions${qs ? `?${qs}` : ""}`);
}

export function getAgentSession(sessionId: string): Promise<AgentSession> {
  return apiJson<AgentSession>(`/agent/sessions/${sessionId}`);
}

export function listAgentMessages(sessionId: string): Promise<{ session_id: string; messages: AgentMessageRecord[] }> {
  return apiJson(`/agent/sessions/${sessionId}/messages`);
}

export function confirmAgentPatch(
  sessionId: string,
  body: { confirm_id: string; approved: boolean },
): Promise<{ status: string; confirm_id: string; profile_id?: string; version?: number }> {
  return apiJson(`/agent/sessions/${sessionId}/confirm`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelAgentRun(sessionId: string): Promise<{ cancelled: boolean }> {
  return apiJson(`/agent/sessions/${sessionId}/cancel`, { method: "POST" });
}

export async function streamAgentMessage(
  sessionId: string,
  body: { content: string; attachments?: AgentAttachment[]; reply_locale?: string },
  onEvent: (event: AgentStreamEvent) => void,
  options?: { signal?: AbortSignal },
): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/sessions/${sessionId}/messages`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      content: body.content,
      attachments: body.attachments ?? [],
      reply_locale: body.reply_locale ?? "zh-CN",
    }),
    signal: options?.signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`Agent stream failed: ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flushBuffer = () => {
    const line = buffer.trim();
    if (!line.startsWith("data:")) return;
    const json = line.slice(5).trim();
    if (json) onEvent(JSON.parse(json) as AgentStreamEvent);
  };

  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() ?? "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        const json = line.slice(5).trim();
        if (json) onEvent(JSON.parse(json) as AgentStreamEvent);
      }
    }
    if (done) {
      buffer += decoder.decode();
      flushBuffer();
      break;
    }
  }
}
