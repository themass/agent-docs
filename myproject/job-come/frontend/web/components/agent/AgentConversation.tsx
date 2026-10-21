"use client";

import { AgentPhotoAction } from "./AgentPhotoAction";
import { AgentMark } from "@/components/agent/AgentMark";
import { UserMark } from "@/components/agent/UserMark";
import {
  AgentConversation as AgentConversationKit,
  type AgentConversationEvents,
  type AgentConversationViewState,
  type AgentUiDisplayItem,
} from "@/lib/agent-ui-kit";
import { jobComeConversationLabels } from "@/lib/agent/jobcome-conversation-labels";
import { userFacingAssistantText } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";
import type { AgentDisplayItem } from "@/lib/types/agent";
import type { useAgentSession } from "@/hooks/useAgentSession";

type Session = ReturnType<typeof useAgentSession>;

type Props = {
  variant?: "default" | "sidebar";
  agent: Session;
  disabled?: boolean;
  placeholder?: string;
  focusHint?: string | null;
  classNames?: { error?: string; focusHint?: string; root?: string };
};

function mapItems(items: AgentDisplayItem[]): AgentUiDisplayItem[] {
  return items as AgentUiDisplayItem[];
}

function buildState(
  agent: Session,
  disabled: boolean | undefined,
  placeholder?: string,
  focusHint?: string | null,
): AgentConversationViewState {
  return {
    busy: agent.busy,
    confirmingId: agent.confirmingId,
    disabled,
    error: agent.error,
    queueWait: agent.queueWait,
    context: agent.contextUsage,
    composerPlaceholder: placeholder,
    focusHint,
    queue: {
      items: agent.followUpQueue.map((q) => ({ id: q.id, content: q.content })),
      priorityCount: agent.steerQueue.length,
    },
  };
}

function buildEvents(agent: Session): AgentConversationEvents {
  return {
    onSend: agent.sendMessage,
    onStop: agent.stopRun,
    onConfirm: agent.resolveConfirm,
    onQueueRemove: agent.removeQueued,
    onQueueReorder: agent.reorderQueued,
    onQueueRunNow: agent.runQueuedNow,
    onQueueEdit: agent.updateQueued,
    onQueueClearPriority: agent.clearSteerQueue,
    onRetry: agent.retryLastMessage,
  };
}

/** JobCome agent conversation — thread + input dock with 舟卡 chrome. */
export function AgentConversation({
  variant = "sidebar",
  agent,
  disabled,
  placeholder,
  focusHint,
  classNames,
}: Props) {
  const { context: authContext } = useAuth();
  const userLabel = authContext?.user?.display_name || authContext?.user?.email || null;
  return (
    <AgentConversationKit
      variant={variant}
      labels={jobComeConversationLabels}
      chrome={{
        renderAgentIcon: (props) => <AgentMark size={props.size} thinking={props.thinking} className={props.className} />,
        renderUserIcon: (props) => <UserMark label={userLabel} size={props.size} className={props.className} />,
        // Replies go through the reply-safe guard. The error sanitizer that used to
        // sit here judged any text over 180 characters to be a stack trace, so a
        // normal long answer was displayed as 「舟卡没能完成这次回复」.
        formatAssistantMessage: userFacingAssistantText,
      }}
      state={buildState(agent, disabled, placeholder, focusHint)}
      events={buildEvents(agent)}
      items={mapItems(agent.items)}
      beforeComposer={
        <AgentPhotoAction
          key={agent.sessionId}
          sessionId={agent.sessionId}
          items={agent.items}
          disabled={disabled || agent.busy}
          onSaved={agent.notifyProfileUpdated}
        />
      }
      classNames={classNames}
    />
  );
}
