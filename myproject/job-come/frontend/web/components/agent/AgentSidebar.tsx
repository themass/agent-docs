"use client";

import { useEffect, useRef, useState } from "react";

import { AgentConversation } from "@/components/agent/AgentConversation";
import { AgentHeader } from "@/components/agent/AgentHeader";
import { AgentHistoryDrawer } from "@/components/agent/AgentHistoryDrawer";
import { useAgentSession } from "@/hooks/useAgentSession";
import { sessionHeaderSubtitle } from "@/lib/agent-session-display";
import { ZHOUKA_NAME } from "@/lib/brand";
import { formatUiFocusChip, type AgentUiContext } from "@/lib/ui-context";

type Props = {
  pageKey: string;
  profileId: string | null;
  jobId?: string | null;
  skillHint: string;
  kind?: string;
  disabled?: boolean;
  placeholder?: string;
  onProfileUpdated?: () => void;
  uiContext?: AgentUiContext | null;
  /** Omitted when the panel cannot be collapsed. */
  onCollapse?: () => void;
  /**
   * An opening turn to send on the user's behalf, used when they entered through a
   * button that promised a conversation ("和舟卡聊着写") rather than through the
   * composer. Keyed so the same request cannot fire twice across re-renders.
   */
  autoStart?: { id: string; message: string } | null;
  /**
   * Lifts run state out so a collapsed rail can show it. The session lives in this
   * component, so the parent has no other way to know a run is in flight.
   */
  onStatusChange?: (status: { busy: boolean; assistantCount: number }) => void;
};

export function AgentSidebar({
  pageKey,
  profileId,
  jobId = null,
  skillHint,
  kind,
  disabled = false,
  placeholder,
  onProfileUpdated,
  uiContext = null,
  onCollapse,
  onStatusChange,
  autoStart = null,
}: Props) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const agent = useAgentSession({
    pageKey,
    profileId,
    jobId,
    skillHint,
    kind,
    disabled,
    onProfileUpdated,
    uiContext,
  });
  const focusChip = formatUiFocusChip(uiContext);

  // Fire-once per request id. The session lives here, so the page that owns the
  // entry button cannot send the turn itself; it hands down the request instead.
  const autoStartedRef = useRef<string | null>(null);
  const sendRef = useRef(agent.sendMessage);
  sendRef.current = agent.sendMessage;
  useEffect(() => {
    if (disabled || !autoStart) return;
    if (autoStartedRef.current === autoStart.id) return;
    autoStartedRef.current = autoStart.id;
    void sendRef.current(autoStart.message);
  }, [autoStart, disabled]);

  // Count *completed* assistant turns. A streaming item would make the collapsed badge
  // tick up on every token, which is noise rather than news.
  const assistantCount = agent.items.filter(
    (item) => item.kind === "assistant" && !item.streaming,
  ).length;

  useEffect(() => {
    onStatusChange?.({ busy: agent.busy, assistantCount });
  }, [agent.busy, assistantCount, onStatusChange]);

  const firstUserLine = agent.items.find((item) => item.kind === "user")?.content;
  const sessionSubtitle = sessionHeaderSubtitle(
    agent.sessions,
    agent.sessionId,
    firstUserLine,
  );

  // Two different queues, and conflating them would mislead. `queueWait` is waiting
  // for the shared harness slot (other users ahead); `followUpQueue` is this user's own
  // messages waiting for their own current turn to finish.
  const statusDetail =
    agent.busy
      ? agent.queueWait
        ? agent.queueWait.ahead > 0
          ? `排队中（前面 ${agent.queueWait.ahead} 个）`
          : "排队中，马上开始"
        : agent.steerQueue.length > 0
          ? `插队纠偏 ×${agent.steerQueue.length}`
          : agent.followUpQueue.length > 0
            ? `排队 ${agent.followUpQueue.length} 条`
            : "正在回复…"
      : undefined;

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-surface-sunken">
      <AgentHeader
        sessionId={agent.sessionId}
        busy={agent.busy}
        sessions={agent.sessions}
        statusDetail={statusDetail}
        sessionSubtitle={sessionSubtitle}
        disabled={disabled}
        replyLocale={agent.replyLocale}
        onReplyLocaleChange={agent.setReplyLocale}
        onNew={agent.resetSession}
        onOpenHistory={() => setHistoryOpen(true)}
        onCollapse={onCollapse}
      />

      <AgentHistoryDrawer
        open={historyOpen}
        sessions={agent.sessions}
        activeId={agent.sessionId}
        onClose={() => setHistoryOpen(false)}
        onSelect={(id) => void agent.resumeSession(id)}
        onNew={agent.resetSession}
      />

      {disabled ? (
        <p className="px-4 py-8 text-center text-sm text-warn-900">请先登录以使用{ZHOUKA_NAME}。</p>
      ) : (
        <>
          <AgentConversation
            variant="sidebar"
            agent={agent}
            disabled={disabled}
            placeholder={placeholder}
            focusHint={focusChip}
          />
        </>
      )}
    </div>
  );
}
