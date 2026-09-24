"use client";

import { AgentStreamPanel } from "@/components/agent/AgentStreamPanel";
import type { AgentDisplayItem } from "@/lib/types/agent";

type Props = {
  items: AgentDisplayItem[];
  busy?: boolean;
  variant?: "default" | "sidebar";
  onConfirm?: (confirmId: string, approved: boolean) => void;
  composer: React.ReactNode;
};

/** Agent message thread (turn-fold) + composer shell. */
export function AgentAssistantPanel({
  items,
  busy = false,
  variant = "default",
  onConfirm,
  composer,
}: Props) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <AgentStreamPanel items={items} busy={busy} variant={variant} onConfirm={onConfirm} />
      {composer}
    </div>
  );
}
