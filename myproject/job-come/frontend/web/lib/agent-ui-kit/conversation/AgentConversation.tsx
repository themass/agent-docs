"use client";

import { AgentInputDock } from "../AgentInputDock";
import { cn } from "../cn";
import { AgentConversationThread } from "./AgentConversationThread";
import type { AgentConversationProps } from "./types";

/**
 * Full agent conversation surface: scrollable thread + input dock (queue, composer).
 * Business logic lives in `state` + `events`; branding in `labels` + `chrome.renderAgentIcon`.
 */
export function AgentConversation({
  variant = "sidebar",
  labels,
  chrome,
  state,
  events,
  items,
  classNames,
  beforeComposer,
}: AgentConversationProps) {
  const errorClass = classNames?.error ?? "shrink-0 px-3 pb-1 text-xs text-danger-600";

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", classNames?.root)}>
      <AgentConversationThread
        items={items}
        busy={state.busy}
        variant={variant}
        labels={labels.thread}
        chrome={chrome}
        onConfirm={events.onConfirm}
        confirmingId={state.confirmingId}
        onRetry={events.onRetry}
      />
      {beforeComposer}
      <AgentInputDock
        variant={variant}
        labels={labels}
        disabled={state.disabled}
        busy={state.busy}
        error={state.error}
        queueWait={state.queueWait}
        focusHint={state.focusHint}
        context={state.context}
        composerPlaceholder={state.composerPlaceholder}
        onSend={events.onSend}
        onStop={events.onStop}
        queue={{
          items: state.queue.items,
          priorityCount: state.queue.priorityCount,
          onRemove: events.onQueueRemove,
          onReorder: events.onQueueReorder,
          onRunNow: events.onQueueRunNow,
          onEdit: events.onQueueEdit,
          onClearPriority: events.onQueueClearPriority,
        }}
        classNames={{
          error: errorClass,
          focusHint: classNames?.focusHint,
        }}
      />
    </div>
  );
}
