"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { logout } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { NotificationCenter } from "@/components/notifications/NotificationCenter";

const NAV = [
  { href: "/resume-agent", label: "简历优化" },
  { href: "/jobs", label: "定向岗位" },
  { href: "/apply-agent", label: "定向申请" },
  { href: "/coach-agent", label: "面试辅导" },
  { href: "/campaign", label: "战役看板" },
  { href: "/bank", label: "题库" },
  { href: "/applications", label: "投递记录" },
  { href: "/admin/sessions", label: "会话审计" },
];

export function AppHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { context, loading, refresh } = useAuth();
  const [pendingHref, setPendingHref] = useState<string | null>(null);

  useEffect(() => {
    setPendingHref(null);
  }, [pathname]);

  async function onLogout() {
    await logout();
    await refresh();
    router.push("/resume-agent");
  }

  return (
    <header className="sticky top-0 z-[10050] border-b border-surface-border bg-white/95 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center justify-between gap-3 px-4">
        <Link href="/resume-agent" className="flex shrink-0 items-center gap-2 font-semibold text-slate-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm text-white">
            J
          </span>
          JobCome
        </Link>
        <nav className="hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto md:flex">
          {NAV.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const pending = pendingHref === item.href && pathname !== item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                prefetch={false}
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
                  if (pathname === item.href) {
                    e.preventDefault();
                    return;
                  }
                  setPendingHref(item.href);
                }}
                className={`shrink-0 rounded-lg px-2.5 py-1.5 text-sm transition ${
                  active
                    ? "bg-brand-50 font-medium text-brand-700"
                    : pending
                      ? "bg-slate-100 font-medium text-slate-800"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {item.label}
                {pending && !active ? <span className="ml-1 text-slate-400">…</span> : null}
              </Link>
            );
          })}
        </nav>
        <div className="flex shrink-0 items-center gap-3 text-sm">
          {loading ? (
            <span className="text-slate-400">…</span>
          ) : context?.actor === "user" ? (
            <>
              <NotificationCenter />
              <span className="hidden max-w-[140px] truncate text-slate-500 sm:inline">
                {context.user?.email}
              </span>
              <Link href="/auth/change-password" className="text-slate-500 hover:text-slate-800">
                改密
              </Link>
              <button
                type="button"
                onClick={onLogout}
                className="rounded-lg px-2 py-1 text-slate-500 hover:bg-slate-50 hover:text-slate-800"
              >
                退出
              </button>
            </>
          ) : (
            <>
              <span className="text-slate-400">访客</span>
              <Link
                href="/auth/login"
                className="rounded-lg bg-brand-600 px-3 py-1.5 text-white hover:bg-brand-700"
              >
                登录
              </Link>
            </>
          )}
        </div>
      </div>
      {pendingHref && pendingHref !== pathname ? (
        <div className="h-0.5 w-full overflow-hidden bg-slate-100">
          <div className="h-full w-1/3 animate-pulse bg-brand-500" />
        </div>
      ) : null}
    </header>
  );
}
