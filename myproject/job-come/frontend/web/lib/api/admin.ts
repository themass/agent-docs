import { apiJson } from "./client";
import type {
  FeedbackCategory,
  FeedbackMessageItem,
  FeedbackStatus,
} from "./feedback";
import type { Profile } from "./profile";

const ADMIN_TOKEN_KEY = "jc_admin_token";

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
  user_display_name: string | null;
  user_email: string | null;
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

/** The order a list is actually being served in; the server echoes what it
 * applied so a header arrow cannot claim an order the rows are not in. */
export type AdminSortState = { sort_by: string; sort_dir: "asc" | "desc" };

/** Request-side half of the pair. Omitted fields mean "the list's own default". */
export type AdminSortQuery = { sort_by?: string; sort_dir?: "asc" | "desc" };

export function listAdminSessions(params?: {
  limit?: number;
  offset?: number;
  user_id?: string;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}): Promise<{ sessions: AdminSessionListItem[]; total: number; limit: number; offset: number } & AdminSortState> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.user_id) q.set("user_id", params.user_id);
  if (params?.search) q.set("search", params.search);
  if (params?.sort_by) q.set("sort_by", params.sort_by);
  if (params?.sort_dir) q.set("sort_dir", params.sort_dir);
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

export type AdminUserListItem = {
  id: string;
  email: string;
  role: string;
  status: string;
  display_name: string | null;
  email_verified: boolean;
  profile_count: number;
  session_count: number;
  created_at: string;
  updated_at: string;
};

export type AdminUserProfileSummary = {
  id: string;
  status: string;
  version: number;
  locale: string;
  contact_name: string | null;
  summary_text: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type AdminUserDetail = AdminUserListItem & {
  locale: string | null;
  default_elevation_level: string | null;
  profiles: AdminUserProfileSummary[];
};

export function listAdminUsers(params?: {
  limit?: number;
  offset?: number;
  search?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}): Promise<{ users: AdminUserListItem[]; total: number; limit: number; offset: number } & AdminSortState> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.search) q.set("search", params.search);
  if (params?.sort_by) q.set("sort_by", params.sort_by);
  if (params?.sort_dir) q.set("sort_dir", params.sort_dir);
  const qs = q.toString();
  return apiJson(`/admin/users${qs ? `?${qs}` : ""}`, { headers: adminHeaders() });
}

export function getAdminUser(userId: string): Promise<AdminUserDetail> {
  return apiJson(`/admin/users/${userId}`, { headers: adminHeaders() });
}

export function getAdminProfile(profileId: string): Promise<Profile> {
  return apiJson(`/admin/profiles/${profileId}`, { headers: adminHeaders() });
}

export type AdminMessageItem = {
  id: string;
  session_id: string;
  role: string;
  event_type: string;
  content: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
};

export type AdminTraceItem = {
  id: string;
  session_id: string;
  seq: number;
  user_id: string | null;
  profile_id: string | null;
  job_id: string | null;
  mock_session_id: string | null;
  trace_id: string | null;
  llm_call_id: string | null;
  event_type: string;
  role: string;
  payload: unknown;
  attachments: unknown[] | null;
  created_at: string;
};

export function getAdminSessionMessages(
  sessionId: string,
  limit = 500,
): Promise<{ session_id: string; messages: AdminMessageItem[]; total: number }> {
  return apiJson(`/admin/sessions/${sessionId}/messages?limit=${limit}`, {
    headers: adminHeaders(),
  });
}

export function getAdminSessionTrace(
  sessionId: string,
  limit = 5000,
): Promise<{ session_id: string; events: AdminTraceItem[]; total: number }> {
  return apiJson(`/admin/sessions/${sessionId}/trace?limit=${limit}`, {
    headers: adminHeaders(),
  });
}


export type AdminFeedbackThreadItem = {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string | null;
  title: string;
  category: FeedbackCategory;
  status: FeedbackStatus;
  last_message_role: "user" | "admin";
  last_message_at: string;
  message_count: number;
  created_at: string;
};

export type AdminFeedbackThreadDetail = AdminFeedbackThreadItem & {
  messages: FeedbackMessageItem[];
};

export function listAdminFeedback(params?: {
  limit?: number;
  offset?: number;
  status?: FeedbackStatus;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}): Promise<{ threads: AdminFeedbackThreadItem[]; total: number; limit: number; offset: number } & AdminSortState> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.status) q.set("status", params.status);
  if (params?.sort_by) q.set("sort_by", params.sort_by);
  if (params?.sort_dir) q.set("sort_dir", params.sort_dir);
  const qs = q.toString();
  return apiJson(`/admin/feedback${qs ? `?${qs}` : ""}`, { headers: adminHeaders() });
}

export function getAdminFeedback(threadId: string): Promise<AdminFeedbackThreadDetail> {
  return apiJson(`/admin/feedback/${threadId}`, { headers: adminHeaders() });
}

export function replyAdminFeedback(
  threadId: string,
  body: string,
): Promise<AdminFeedbackThreadDetail> {
  return apiJson(`/admin/feedback/${threadId}/reply`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ body }),
  });
}

export function setAdminFeedbackStatus(
  threadId: string,
  status: FeedbackStatus,
): Promise<AdminFeedbackThreadDetail> {
  return apiJson(`/admin/feedback/${threadId}/status`, {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ status }),
  });
}


export type AdminLlmAttemptItem = {
  attempt_index: number;
  model: string;
  provider: string | null;
  api_base_env: string | null;
  status: string;
  error_code: string | null;
  error_message: string | null;
  validator_failed: boolean;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  reasoning_tokens: number | null;
  total_tokens: number | null;
  cost_micro_usd: number | null;
};

export type AdminLlmCallItem = {
  id: string;
  user_id: string | null;
  user_display_name: string | null;
  user_email: string | null;
  actor_kind: string | null;
  profile_id: string | null;
  job_id: string | null;
  session_id: string | null;
  scenario: string;
  caller: string;
  channel: string;
  skill_hint: string | null;
  status: string;
  final_model: string | null;
  final_provider: string | null;
  attempt_count: number;
  error_code: string | null;
  error_message: string | null;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  reasoning_tokens: number | null;
  total_tokens: number | null;
  cost_micro_usd: number | null;
  trace_id: string | null;
  stream: boolean;
  payload_truncated: boolean;
  created_at: string;
};

export type AdminLlmCallDetail = AdminLlmCallItem & {
  attempts: AdminLlmAttemptItem[];
  prompt_text: string | null;
  response_text: string | null;
  reasoning_text: string | null;
};

export type AdminLlmUsageRow = {
  key: string | null;
  calls: number;
  failed: number;
  total_tokens: number;
  cost_micro_usd: number;
  avg_latency_ms: number;
};

export function listAdminLlmCalls(params?: {
  limit?: number;
  offset?: number;
  user_id?: string;
  profile_id?: string;
  scenario?: string;
  caller?: string;
  channel?: string;
  status?: string;
  trace_id?: string;
  sort_by?: string;
  sort_dir?: "asc" | "desc";
}): Promise<{ calls: AdminLlmCallItem[]; total: number; limit: number; offset: number } & AdminSortState> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  if (params?.user_id) q.set("user_id", params.user_id);
  if (params?.profile_id) q.set("profile_id", params.profile_id);
  if (params?.scenario) q.set("scenario", params.scenario);
  if (params?.caller) q.set("caller", params.caller);
  if (params?.channel) q.set("channel", params.channel);
  if (params?.status) q.set("status", params.status);
  if (params?.trace_id) q.set("trace_id", params.trace_id);
  if (params?.sort_by) q.set("sort_by", params.sort_by);
  if (params?.sort_dir) q.set("sort_dir", params.sort_dir);
  const qs = q.toString();
  return apiJson(`/admin/llm/calls${qs ? `?${qs}` : ""}`, { headers: adminHeaders() });
}

export function getAdminLlmCall(
  callId: string,
  includePayload = false,
): Promise<AdminLlmCallDetail> {
  const qs = includePayload ? "?include_payload=true" : "";
  return apiJson(`/admin/llm/calls/${callId}${qs}`, { headers: adminHeaders() });
}

export function getAdminLlmUsage(params?: {
  days?: number;
  group_by?: "scenario" | "caller" | "channel" | "final_model" | "status";
}): Promise<{ group_by: string; days: number; rows: AdminLlmUsageRow[] }> {
  const q = new URLSearchParams();
  if (params?.days) q.set("days", String(params.days));
  if (params?.group_by) q.set("group_by", params.group_by);
  const qs = q.toString();
  return apiJson(`/admin/llm/usage${qs ? `?${qs}` : ""}`, { headers: adminHeaders() });
}
