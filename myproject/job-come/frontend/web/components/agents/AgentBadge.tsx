import type { Agent } from "@/lib/agents";

/** The agent's mark: a coloured tile with its initial. Shown wherever the agent is named. */
export function AgentBadge({ agent, size = "md" }: { agent: Agent; size?: "sm" | "md" }) {
  const dims = size === "sm" ? "h-6 w-6 text-xs" : "h-9 w-9 text-sm";
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-lg font-semibold text-white ${dims} ${agent.tone}`}
    >
      {agent.initial}
    </span>
  );
}
