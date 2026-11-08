// Where a page remembers which agent chat it is showing. One chat holds one DeerFlow thread, and
// that thread keeps every turn it has seen. So a chat must not carry more than one mock interview:
// starting a new interview forgets the remembered chat, and the next message opens a fresh one.

export function chatStorageKey(pageKey: string, profileId: string | null): string {
  return `jc_agent_session_${pageKey}_${profileId ?? "none"}`;
}

export function forgetStoredChat(
  storage: Pick<Storage, "removeItem">,
  pageKey: string,
  profileId: string | null,
): void {
  storage.removeItem(chatStorageKey(pageKey, profileId));
}
