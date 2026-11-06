import type { AgentAttachment, AgentDisplayItem } from "@/lib/types/agent";

/**
 * What a retry sends, for the user bubble `itemId`: its text and attachments, the id it was first
 * sent with (so the server does not record its answer twice), and the items that come before it,
 * which stay on screen. Null when the id is not a user message.
 */
export function retryPlan(
  items: AgentDisplayItem[],
  itemId: string,
): {
  kept: AgentDisplayItem[];
  content: string;
  attachments: AgentAttachment[];
  clientMessageId?: string;
} | null {
  const index = items.findIndex((item) => item.id === itemId);
  const target = index >= 0 ? items[index] : undefined;
  if (!target || target.kind !== "user") return null;
  return {
    kept: items.slice(0, index),
    content: target.content,
    attachments: target.attachments ?? [],
    clientMessageId: target.clientMessageId,
  };
}
