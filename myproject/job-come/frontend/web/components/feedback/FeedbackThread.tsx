"use client";

import { AgentAvatarMark } from "@/lib/agent-ui-kit";
import { UserMark } from "@/components/agent/UserMark";
import type { FeedbackMessageItem, FeedbackMessageRole } from "@/lib/api/feedback";
import { formatDateTime } from "@/lib/datetime";

/**
 * Shared IM-style transcript for a feedback thread. Rendered by both the
 * user's own thread page and the admin reply drawer — only `viewerRole`
 * differs, which flips which side of the thread is "me" (right-aligned,
 * brand-tinted bubble) versus "them" (left-aligned, neutral bubble). This
 * keeps the two surfaces visually identical except for that one framing
 * difference, same as the agent chat's own user/assistant bubble split.
 */
export function FeedbackThread({
  messages,
  viewerRole,
  userLabel,
}: {
  messages: FeedbackMessageItem[];
  viewerRole: FeedbackMessageRole;
  /** First-character label for the user-role mark; admin viewers pass the submitter's name. */
  userLabel?: string | null;
}) {
  if (messages.length === 0) {
    return <p className="text-sm text-ink-500">暂无消息。</p>;
  }

  return (
    <ul className="flex flex-col gap-3">
      {messages.map((m) => (
        <FeedbackMessageRow key={m.id} message={m} viewerRole={viewerRole} userLabel={userLabel} />
      ))}
    </ul>
  );
}

function FeedbackMessageRow({
  message,
  viewerRole,
  userLabel,
}: {
  message: FeedbackMessageItem;
  viewerRole: FeedbackMessageRole;
  userLabel?: string | null;
}) {
  const isMine = message.role === viewerRole;
  return (
    <li className={`flex items-start gap-2 ${isMine ? "flex-row-reverse" : ""}`}>
      {message.role === "admin" ? (
        <AgentAvatarMark label="客服" size={28} className="shrink-0" />
      ) : (
        <UserMark label={userLabel} size={28} className="shrink-0" />
      )}
      <div className={`flex min-w-0 max-w-[80%] flex-col gap-1 ${isMine ? "items-end" : "items-start"}`}>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
            isMine
              ? "bg-brand-600 text-white"
              : "bg-ink-100 text-ink-800"
          }`}
        >
          {message.body}
        </div>
        <p className="px-1 text-micro text-ink-400">
          {message.role === "admin" ? "客服" : "我"} · {formatDateTime(message.created_at)}
        </p>
      </div>
    </li>
  );
}
