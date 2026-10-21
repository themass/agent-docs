"use client";

import { AgentHarnessWaitNotice } from "./AgentHarnessWaitNotice";
import { AgentMessageQueue } from "./AgentMessageQueue";
import { AgentComposer } from "./composer/AgentComposer";
import type { AgentInputDockProps } from "./types";

/**
 * Full agent chrome below the thread: harness wait notice, follow-up queue, and composer.
 * One import for Cursor/Codex-style “input dock” portability.
 */
export function AgentInputDock({
  variant = "sidebar",
  labels,
  disabled = false,
  busy = false,
  error,
  queueWait,
  queue,
  focusHint,
  context,
  composerPlaceholder,
  onSend,
  onStop,
  classNames,
}: AgentInputDockProps) {
  const errorClass = classNames?.error ?? "shrink-0 px-3 pb-1 text-xs text-danger-600";
  const focusClass = classNames?.focusHint ?? "shrink-0 px-3 pb-1 text-xs text-brand-700";

  return (
    <>
      {error ? <p className={errorClass}>{error}</p> : null}
      <AgentHarnessWaitNotice
        wait={queueWait}
        labels={labels.wait}
        className={variant === "sidebar" ? undefined : "mx-4"}
      />
      <AgentMessageQueue
        items={queue.items}
        busy={busy}
        priorityCount={queue.priorityCount ?? 0}
        labels={labels.queue}
        onRemove={queue.onRemove}
        onReorder={queue.onReorder}
        onRunNow={queue.onRunNow}
        onEdit={queue.onEdit}
        onClearPriority={queue.onClearPriority}
        classNames={classNames}
      />
      {focusHint ? (
        <p className={focusClass}>
          {labels.focusPrefix ?? ""}
          {focusHint}
        </p>
      ) : null}
      <AgentComposer
        variant={variant}
        disabled={disabled}
        busy={busy}
        context={context}
        labels={labels.composer}
        placeholder={composerPlaceholder}
        onSend={onSend}
        onStop={onStop}
      />
    </>
  );
}
