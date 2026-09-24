import type { AgentContextBucket, AgentContextUsage, AgentDisplayItem } from "@/lib/types/agent";

const DEFAULT_LIMIT = 200_000;

const BASE_BUCKETS: AgentContextBucket[] = [
  { id: "system_prompt", label: "System prompt", tokens: 800 },
  { id: "tool_definitions", label: "Tool definitions", tokens: 4_500 },
  { id: "skills", label: "Skills", tokens: 2_200 },
  { id: "rules", label: "Rules", tokens: 900 },
];

function estimateTokensFromText(text: string): number {
  return Math.ceil(text.length / 2);
}

export function estimateConversationTokens(items: AgentDisplayItem[]): number {
  let chars = 0;
  for (const item of items) {
    if (item.kind === "user" || item.kind === "assistant") chars += item.content.length;
    if (item.kind === "thinking") chars += item.content.length;
    if (item.kind === "tool_result") chars += item.result.length;
  }
  return estimateTokensFromText(String(chars));
}

export function buildContextUsage(
  items: AgentDisplayItem[],
  usage: { prompt: number; completion: number; total: number; turns: number },
  server?: AgentContextUsage | null,
  limit = DEFAULT_LIMIT,
): AgentContextUsage {
  if (server) {
    return {
      ...server,
      limit_tokens: server.limit_tokens || limit,
      turns: usage.turns,
    };
  }

  const conversation = Math.max(estimateConversationTokens(items), usage.prompt);
  const buckets: AgentContextBucket[] = [
    ...BASE_BUCKETS,
    { id: "conversation", label: "Conversation", tokens: conversation },
  ];
  const used = buckets.reduce((sum, b) => sum + b.tokens, 0);
  return {
    limit_tokens: limit,
    used_tokens: used,
    percent: Math.min(100, Math.round((used / limit) * 100)),
    estimated: true,
    buckets,
    turns: usage.turns,
    actual: usage.total > 0
      ? { prompt_tokens: usage.prompt, completion_tokens: usage.completion, total_tokens: usage.total }
      : undefined,
  };
}
