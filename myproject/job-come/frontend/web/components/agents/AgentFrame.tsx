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
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <header className="flex flex-wrap items-center gap-3">
        <AgentBadge agent={agent} />
        <div className="min-w-0">
          <p className="text-base font-semibold text-ink-900">{agent.name}</p>
          <p className="text-xs text-ink-600">{agent.promise}</p>
        </div>
      </header>
      <nav aria-label={`${agent.name}的页面`} className="segment w-fit max-w-full flex-wrap">
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
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
