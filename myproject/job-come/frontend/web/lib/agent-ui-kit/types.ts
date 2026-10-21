import type { ReactNode } from "react";

/** Minimal queue row — host may attach more fields on their own type. */
export type AgentQueueItem = {
  id: string;
  content: string;
};

export type AgentUiKitClassNames = {
  avatar?: string;
  avatarThinking?: string;
  thinkingPill?: string;
  thinkingInline?: string;
  thinkingDots?: string;
  queueRoot?: string;
  queueHeaderButton?: string;
  queueTitle?: string;
  queueBadge?: string;
  queueHint?: string;
  queueChevron?: string;
  queuePriorityBanner?: string;
  queuePriorityTitle?: string;
  queuePriorityClear?: string;
  queuePriorityHint?: string;
  queueRow?: string;
  queueRowDragging?: string;
  queueRowDropTarget?: string;
  queueGrip?: string;
  queueIndex?: string;
  queueBody?: string;
  queueEditArea?: string;
  queueIconButton?: string;
  queueIconButtonDanger?: string;
  queueIconButtonAccent?: string;
};

export type AgentMessageQueueLabels = {
  title: string;
  hintBusy: string;
  hintIdle: string;
  priorityTitle: (count: number) => string;
  priorityClear: string;
  priorityHint: string;
  dragHandleTitle: string;
  runNowTitle: (busy: boolean) => string;
  runNowAria: (busy: boolean) => string;
  editTitle: string;
  editAria: string;
  removeTitle: string;
  removeAria: string;
  saveEditTitle: string;
  saveEditAria: string;
  cancelEditTitle: string;
  cancelEditAria: string;
};

export type AgentThinkingIndicatorProps = {
  /** Text before animated dots, e.g. "舟卡思考中" or "Agent thinking". */
  label: string;
  variant?: "pill" | "inline";
  /** Optional avatar slot (mark, image, icon). */
  avatar?: ReactNode;
  className?: string;
  classNames?: Partial<AgentUiKitClassNames>;
};

export type AgentAvatarMarkProps = {
  label: string;
  size?: number;
  thinking?: boolean;
  className?: string;
  classNames?: Partial<AgentUiKitClassNames>;
};

export type AgentComposerAttachment = {
  kind: "image" | "file" | "audio";
  name: string;
  label?: string | null;
  mime_type?: string | null;
  data_url?: string | null;
  text_preview?: string | null;
  size_bytes?: number | null;
  transcript?: string | null;
  duration_ms?: number | null;
};

export type AgentContextBucket = {
  id: string;
  label: string;
  tokens: number;
};

export type AgentContextUsage = {
  used_tokens: number;
  limit_tokens: number;
  percent: number;
  estimated: boolean;
  buckets: AgentContextBucket[];
  turns: number;
  actual?: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
};

export type AgentHarnessWait = {
  waitedSec: number;
  ahead: number;
};

export type AgentHarnessWaitLabels = {
  title: (position: string) => string;
  positionAhead: (ahead: number) => string;
  positionNext: string;
  body: (seconds: number) => string;
};

/**
 * Camera capture panel (`CameraPage`) copy. Grouped on its own because the panel
 * is a fixed-position portal with its own phase machine (live/review/blocked),
 * not a simple label-per-button surface.
 */
export type AgentCameraLabels = {
  /** Title bar text, e.g. "拍照". */
  panelTitle: string;
  dragPanelTitle: string;
  closeAria: string;
  /** Shown when the browser has no `getUserMedia` support at all. */
  unsupported: string;
  /** Fallback when a specific camera error has no mapped message. */
  blockedFallback: string;
  retry: string;
  previewAlt: string;
  retake: string;
  useThisShot: string;
  opening: string;
  preparingPreview: string;
  flip: string;
  shutterAria: string;
  captureFailed: string;
};

/** Recorded voice clip (`VoiceCard`) copy — both the composer preview and the chat bubble read this. */
export type AgentVoiceCardLabels = {
  /** Shown instead of a player when the clip failed to upload to storage. */
  uploadFailed: string;
  noTranscript: string;
  removeAria: string;
};

/** Live recording strip (`VoiceCaptureBar`) copy. */
export type AgentVoiceCaptureBarLabels = {
  listening: string;
  waitingForSpeech: string;
  autoStopHint: string;
  cancel: string;
  finish: string;
};

/** Full-size image viewer (`ZoomableImage` / its lightbox) copy. */
export type AgentImageViewerLabels = {
  zoomAria: string;
  closeAria: string;
};

/** Inline audio player (`CompactAudioPlayer`) copy. */
export type AgentAudioPlayerLabels = {
  play: string;
  pause: string;
  progressAria: string;
};

export type AgentComposerLabels = {
  placeholderDefault: string;
  placeholderBusy: string;
  placeholderListening: string;
  dropOverlay: string;
  removeAttachmentAria: string;
  voiceClipLabel: string;
  voiceClipSizeLabel: string;
  cameraShotLabel: string;
  cameraShotSizeLabel: string;
  micMissing: string;
  micDenied: string;
  speechUnsupported: string;
  speechStartFailed: string;
  attachMenuTitle: string;
  attachImage: string;
  attachFile: string;
  attachPasteHint: string;
  cameraTitle: string;
  voiceUiBarTitle: string;
  voiceUiOrbTitle: string;
  voiceStopTitle: string;
  voiceStartTitle: string;
  voiceUnsupportedTitle: string;
  voiceUnsupportedAria: string;
  sendTitle: string;
  sendAria: string;
  stopTitle: string;
  stopAria: string;
  footerHint: (contextPercent: number) => string;
  /** Shown in the floating voice orb before any speech is detected. */
  voiceOrbIdleHint: string;
  /** Shown under the live transcript in the floating voice orb, e.g. drag + auto-stop hints. */
  voiceOrbDragHint: string;
  voiceOrbCancel: string;
  voiceOrbFinish: string;
  camera: AgentCameraLabels;
  voiceCard: AgentVoiceCardLabels;
  voiceCaptureBar: AgentVoiceCaptureBarLabels;
  imageViewer: AgentImageViewerLabels;
  audioPlayer: AgentAudioPlayerLabels;
  /** Close aria-label for the sidebar Context Usage popover (`TokenMeter`). */
  tokenMeterCloseAria: string;
};

export type AgentInputDockLabels = {
  queue: AgentMessageQueueLabels;
  wait: AgentHarnessWaitLabels;
  composer: AgentComposerLabels;
  /** e.g. "Focus: " — shown before `focusHint`. */
  focusPrefix?: string;
};

export type AgentInputDockProps = {
  variant?: "default" | "sidebar";
  labels: AgentInputDockLabels;
  disabled?: boolean;
  busy?: boolean;
  error?: string | null;
  queueWait?: AgentHarnessWait | null;
  queue: {
    items: AgentQueueItem[];
    priorityCount?: number;
    onRemove: (id: string) => void;
    onReorder: (id: string, toIndex: number) => void;
    onRunNow: (id: string) => void;
    onEdit: (id: string, content: string) => void;
    onClearPriority?: () => void;
  };
  focusHint?: string | null;
  context: AgentContextUsage;
  composerPlaceholder?: string;
  onSend: (
    content: string,
    attachments: AgentComposerAttachment[],
    mode?: "send" | "follow_up" | "steer",
  ) => void | Promise<void>;
  onStop?: () => void;
  classNames?: Partial<AgentUiKitClassNames> & {
    error?: string;
    focusHint?: string;
  };
};

export type AgentMessageQueueProps = {
  items: AgentQueueItem[];
  busy: boolean;
  /** High-priority / steer bucket count (optional). */
  priorityCount?: number;
  labels: AgentMessageQueueLabels;
  onRemove: (id: string) => void;
  onReorder: (id: string, toIndex: number) => void;
  onRunNow: (id: string) => void;
  onEdit: (id: string, content: string) => void;
  onClearPriority?: () => void;
  classNames?: Partial<AgentUiKitClassNames>;
  defaultOpen?: boolean;
};
