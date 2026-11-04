"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { AgentBadge } from "@/components/agents/AgentBadge";
import { agentById, type AgentId } from "@/lib/agents";

/**
 * The frame every agent page and its record pages sit in: who the agent is, what it promises, and
 * the tabs to its conversation and the records it produced. The agent is the first thing shown.
 */
export function AgentFrame({ agentId, children }: { agentId: AgentId; children: React.ReactNode }) {
  const pathname = usePathname();
  const agent = agentById(agentId);
  const tabs = [{ href: agent.home, label: "对话" }, ...agent.records];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      {/* One row: the agent's identity and its tabs. The promise is the first thing to go on a
          narrow screen; the page below it is the content the user came for. */}
      <header className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-2">
        <div className="flex min-w-0 items-center gap-2">
          <AgentBadge agent={agent} size="sm" />
          <p className="shrink-0 text-sm font-semibold text-ink-900">{agent.name}</p>
          <p className="hidden min-w-0 truncate text-xs text-ink-500 md:block">{agent.promise}</p>
        </div>
        <nav aria-label={`${agent.name}的页面`} className="segment ml-auto w-fit max-w-full flex-wrap">
          {tabs.map((tab) => {
            const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                prefetch={false}
                aria-current={active ? "page" : undefined}
                className={`segment-item ${active ? "segment-item-active" : ""}`}
              >
                {tab.label}
              </Link>
            );
          })}
  </nav>
      </header>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
