"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ADMIN_TABS = [
  { href: "/admin/users", label: "用户目录" },
  { href: "/admin/sessions", label: "Session 审计" },
  { href: "/admin/llm", label: "LLM 调用" },
  { href: "/admin/feedback", label: "用户反馈" },
] as const;

export function AdminSubNav() {
  const pathname = usePathname();
  return (
    <nav className="flex shrink-0 items-center gap-1 border-b border-surface-border bg-surface px-4 py-2">
      {ADMIN_TABS.map((tab) => {
        const active = pathname.startsWith(tab.href);
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
              active ? "bg-brand-50 text-brand-700" : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
            }`}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}
