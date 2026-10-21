import type { ReactNode } from "react";

import type {
  AgentAudioPlayerLabels,
  AgentComposerAttachment,
  AgentContextUsage,
  AgentHarnessWait,
  AgentImageViewerLabels,
  AgentInputDockLabels,
  AgentQueueItem,
  AgentVoiceCardLabels,
} from "../types";
import type { AgentUiDisplayItem } from "./display-items";

export type AgentSendMode = "send" | "follow_up" | "steer";

/** Replaceable agent avatar in thread + thinking states. */
export type AgentConversationIconProps = {
  size: number;
  thinking?: boolean;
  className?: string;
};

export type AgentPlanTodosLabels = {
  /** Section header, e.g. "计划步骤". */
  sectionTitle: string;
  /** Fallback when a todo has neither `content` nor `id`. */
  defaultTaskLabel: string;
};

export type AgentConversationThreadLabels = {
  emptyTitle: string;
  emptyHint: string;
  /** Tooltip/aria-label on the retry button that appears on a failed message. */
  retryLabel: string;
  /** Prefix before animated dots, e.g. "舟卡思考中". */
  thinkingLabel: string;
  toolsRunning: (count: number) => string;
  stepsDone: (count: number) => string;
  /** Headline when the turn's steps ran but the turn itself ended in error, so the
   *  collapsed card does not read as success right above a failure bubble. */
  stepsFailed: (count: number) => string;
  expand: string;
  collapse: string;
  confirmTitle: string;
  /** One line under the title on a still-pending confirm, telling the user the
   *  change is not saved until they act. Only shown on the standalone pending
   *  card, not on the compact record of an already-answered one. */
  confirmPendingHint: string;
  confirmApprove: string;
  confirmReject: string;
  confirmApplied: string;
  confirmAppliedDetail: string;
  confirmSaving: string;
  confirmRejected: string;
  confirmSuperseded: string;
  subagentRunning: string;
  subagentDone: string;
  toolWaiting: string;
  planTodos: AgentPlanTodosLabels;
  /** Fallback file-type label in the user bubble when a file attachment has no mime type. */
  fileAttachmentFallback: string;
  /** Copy for the attachment renderers inside a replayed user bubble (image zoom, voice clip, audio player). */
  userAttachments: {
    imageViewer: AgentImageViewerLabels;
    voiceCard: AgentVoiceCardLabels;
    audioPlayer: AgentAudioPlayerLabels;
  };
};

export type AgentConversationLabels = AgentInputDockLabels & {
  thread: AgentConversationThreadLabels;
};

export type AgentConversationQueueState = {
  items: AgentQueueItem[];
  priorityCount?: number;
};

export type AgentConversationViewState = {
  busy: boolean;
  /** Confirm card waiting on the server after the user clicked 确认/拒绝. */
  confirmingId?: string | null;
  disabled?: boolean;
  error?: string | null;
  queueWait?: AgentHarnessWait | null;
  queue: AgentConversationQueueState;
  context: AgentContextUsage;
  composerPlaceholder?: string;
  focusHint?: string | null;
};

/** Outbound events — wire to your session / API layer. */
export type AgentConversationEvents = {
  onSend: (
    content: string,
    attachments: AgentComposerAttachment[],
    mode?: AgentSendMode,
  ) => void | Promise<void>;
  onStop?: () => void;
  onConfirm?: (confirmId: string, approved: boolean) => void;
  /** Re-send a user message whose turn ended without a reply (`item.failed`). */
  onRetry?: (itemId: string) => void;
  onQueueRemove: (id: string) => void;
  onQueueReorder: (id: string, toIndex: number) => void;
  onQueueRunNow: (id: string) => void;
  onQueueEdit: (id: string, content: string) => void;
  onQueueClearPriority?: () => void;
};

export type AgentConversationChrome = {
  renderAgentIcon: (props: AgentConversationIconProps) => ReactNode;
  /** User-side avatar mark shown next to their own bubbles. Omit to render no mark. */
  renderUserIcon?: (props: AgentConversationIconProps) => ReactNode;
  /** Sanitize assistant text for display (optional). */
  formatAssistantMessage?: (content: string) => string;
};

export type AgentConversationProps = {
  /** Host-owned contextual actions; the kit has no business-specific dependencies. */
  beforeComposer?: ReactNode;
  variant?: "default" | "sidebar";
  labels: AgentConversationLabels;
  chrome: AgentConversationChrome;
  state: AgentConversationViewState;
  events: AgentConversationEvents;
  items: AgentUiDisplayItem[];
  classNames?: {
    root?: string;
    error?: string;
    focusHint?: string;
  };
};
