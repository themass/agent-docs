import { apiJson } from "./client";

const ADMIN_TOKEN_KEY = "jobcome_admin_token";

export function getAdminToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(ADMIN_TOKEN_KEY) ?? "";
}

export function setAdminToken(token: string): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

function adminHeaders(): HeadersInit {
  const token = getAdminToken();
  return token ? { "X-Admin-Token": token } : {};
}

export type AdminSessionListItem = {
  id: string;
  user_id: string;
  profile_id: string | null;
  job_id: string | null;
  kind: string;
  status: string;
  skill_hint: string | null;
  deerflow_thread_id: string;
  trace_id: string | null;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminTimelineTurn = {
  turn_index: number;
  user_message: string | null;
  user_attachments: Array<Record<string, unknown>>;
  assistant_message: string | null;
  events: Array<{
    id: string;
    event_type: string;
    role: string;
    content: string | null;
    payload: Record<string, unknown> | null;
    created_at: string;
  }>;
  started_at: string | null;
  ended_at: string | null;
};

export type AdminCheckpointMessage = {
  index: number;
  role: string;
  content: unknown;
  tool_calls: Array<Record<string, unknown>>;
  tool_name: string | null;
  tool_call_id: string | null;
  additional_kwargs: Record<string, unknown>;
  usage_metadata: Record<string, unknown> | null;
};

export type AdminInventory = {
  mcp_servers: Array<{
    name: string;
    enabled: boolean;
    type: string | null;
    description: string | null;
    command: string | null;
    args: string[];
    tools: string[];
    resources: Array<{
      uri: string;
      name: string;
      description: string | null;
      mime_type: string | null;
    }>;
  }>;
  middlewares: string[];
  mcp_interceptors: string[];
  tools: Array<{
    name: string;
    description: string | null;
    parameters: Record<string, unknown>;
    registered_on_mcp_server: boolean;
    skills: string[];
  }>;
  skills: Array<{
    id: string;
    enabled: boolean;
    description: string | null;
    body_preview: string | null;
    tools: string[];
    scope_for_hints: string[];
  }>;
  models: Array<Record<string, unknown>>;
  subagents: Array<Record<string, unknown>>;
  product_rules_preview: string | null;
};

export function listAdminSessions(params?: {
  limit?: number;
  offset?: number;
  user_id?: string;
}): Promise<{ sessions: AdminSessionListItem[]; total: number; limit: number; offset: number }> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.user_id) q.set("user_id", params.user_id);
  const qs = q.toString();
  return apiJson(`/admin/sessions${qs ? `?${qs}` : ""}`, { headers: adminHeaders() });
}

export function getAdminSession(sessionId: string): Promise<AdminSessionListItem> {
  return apiJson(`/admin/sessions/${sessionId}`, { headers: adminHeaders() });
}

export function getAdminTimeline(sessionId: string): Promise<{
  session_id: string;
  deerflow_thread_id: string;
  turns: AdminTimelineTurn[];
  raw_message_count: number;
}> {
  return apiJson(`/admin/sessions/${sessionId}/timeline`, { headers: adminHeaders() });
}

export function getAdminCheckpoint(sessionId: string): Promise<{
  session_id: string;
  deerflow_thread_id: string;
  checkpoint_count: number;
  latest_checkpoint_id: string | null;
  summaries: Array<{ checkpoint_id: string; parent_checkpoint_id: string | null; ts: string | null; message_count: number }>;
  messages: AdminCheckpointMessage[];
  skill_context: Record<string, unknown>;
  thread_data: Record<string, unknown>;
}> {
  return apiJson(`/admin/sessions/${sessionId}/checkpoint`, { headers: adminHeaders() });
}

export function getAdminInventory(): Promise<AdminInventory> {
  return apiJson("/admin/inventory", { headers: adminHeaders() });
}
