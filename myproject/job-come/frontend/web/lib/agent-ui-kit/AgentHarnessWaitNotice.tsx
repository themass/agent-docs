"use client";

import type { AgentHarnessWait, AgentHarnessWaitLabels } from "./types";

type Props = {
  wait: AgentHarnessWait | null | undefined;
  labels: AgentHarnessWaitLabels;
  className?: string;
};

export function AgentHarnessWaitNotice({ wait, labels, className }: Props) {
  if (!wait) return null;

  const seconds = Math.max(1, Math.round(wait.waitedSec));
  const position =
    wait.ahead > 0 ? labels.positionAhead(wait.ahead) : labels.positionNext;

  return (
    <div className={className ?? "notice notice-info mx-3 mb-2 shrink-0 text-xs"} role="status" aria-live="polite">
      <div>
        <p className="font-medium">{labels.title(position)}</p>
        <p className="mt-0.5 leading-relaxed opacity-80">{labels.body(seconds)}</p>
      </div>
    </div>
  );
}
