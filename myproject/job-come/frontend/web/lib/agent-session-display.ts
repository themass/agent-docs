import type { AgentSessionListItem } from "@/lib/api/agent";
import { AGENTS } from "@/lib/agents";
import { formatDateTime } from "@/lib/datetime";

/** Agent panel header: keep the subtitle line to one short label (narrow rail). */
export const AGENT_HEADER_LABEL_MAX = 6;

export function truncateAgentHeaderLabel(text: string, max = AGENT_HEADER_LABEL_MAX): string {
  const t = text.trim().replace(/\s+/g, " ");
  if (!t) return t;
  if (t.length <= max) return t;
  return `${t.slice(0, max)}…`;
}

/** Primary line in session history — never the raw session id. */
export function sessionListTitle(session: AgentSessionListItem): string {
  const title = session.title?.trim();
  if (title) return title;
  const agent = AGENTS.find((a) => a.roleId === session.role_id);
  return agent ? `${agent.name}对话` : "智能体对话";
}

/** Secondary line: time only (id is dev-only). */
export function sessionListMeta(session: AgentSessionListItem): string {
  return formatDateTime(session.updated_at);
}

export function sessionHeaderSubtitle(
  sessions: AgentSessionListItem[],
  sessionId: string | null,
  firstUserLine?: string | null,
): string {
  if (!sessionId) return "新对话";
  const fromApi = sessions.find((s) => s.id === sessionId)?.title?.trim();
  if (fromApi) return truncateAgentHeaderLabel(fromApi);
  const local = firstUserLine?.trim().replace(/\s+/g, " ");
  if (local) return truncateAgentHeaderLabel(local);
  return "新对话";
}
