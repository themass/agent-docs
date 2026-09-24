"use client";

import { useState } from "react";

import { AgentAssistantPanel } from "@/components/agent/AgentAssistantPanel";
import { AgentComposerSwitch } from "@/components/agent/AgentComposerSwitch";
import { AgentHeader } from "@/components/agent/AgentHeader";
import { AgentHistoryDrawer } from "@/components/agent/AgentHistoryDrawer";
import { AgentTaskQueue } from "@/components/agent/AgentTaskQueue";
import { useAgentSession } from "@/hooks/useAgentSession";

type Props = {
  pageKey: string;
  profileId: string | null;
  jobId?: string | null;
  skillHint: string;
  kind?: string;
  disabled?: boolean;
  placeholder?: string;
  onProfileUpdated?: () => void;
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
  });

  const statusDetail =
    agent.busy
      ? agent.steerQueue.length > 0
        ? `插队纠偏 ×${agent.steerQueue.length}`
        : agent.followUpQueue.length > 0
          ? `排队 ${agent.followUpQueue.length} 条`
          : "处理中"
      : undefined;

  return (
    <div className="relative flex h-full min-h-0 flex-col bg-[#f8f9fb]">
      <AgentHeader
        sessionId={agent.sessionId}
        busy={agent.busy}
        sessions={agent.sessions}
        statusDetail={statusDetail}
        disabled={disabled}
        replyLocale={agent.replyLocale}
        onReplyLocaleChange={agent.setReplyLocale}
        onNew={agent.resetSession}
        onOpenHistory={() => setHistoryOpen(true)}
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
        <p className="px-4 py-8 text-center text-sm text-amber-800">请先登录以使用 Agent。</p>
      ) : (
        <>
          <AgentAssistantPanel
            variant="sidebar"
            items={agent.items}
            busy={agent.busy}
            onConfirm={agent.resolveConfirm}
            composer={
              <>
                {agent.error ? (
                  <p className="shrink-0 px-3 pb-1 text-xs text-red-600">{agent.error}</p>
                ) : null}
                <AgentTaskQueue
                  followUp={agent.followUpQueue}
                  steerCount={agent.steerQueue.length}
                  busy={agent.busy}
                  onRemove={agent.removeQueued}
                  onClearSteer={agent.clearSteerQueue}
                />
                <AgentComposerSwitch
                  variant="sidebar"
                  disabled={disabled}
                  busy={agent.busy}
                  context={agent.contextUsage}
                  placeholder={placeholder}
                  onSend={agent.sendMessage}
                  onStop={agent.stopRun}
                />
              </>
            }
          />
        </>
      )}
    </div>
  );
}
