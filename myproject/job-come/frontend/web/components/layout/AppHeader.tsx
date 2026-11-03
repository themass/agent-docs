"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AgentBadge } from "@/components/agents/AgentBadge";
import { logout } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
import { isWorkbenchPath } from "@/lib/layout/workbench";
import { AGENTS, OVERVIEW, agentOfPath } from "@/lib/agents";
import { NotificationCenter } from "@/components/notifications/NotificationCenter";

/**
 * Navigation is grouped by the user's actual job-change workflow rather than
 * presented as eight equal-weight links. Eight flat items give no sense of where
 * you are in the process, which is most of why the old header felt like an
 * admin panel.
 *
 * `准备` (get your material ready) comes before `行动` (go after roles) because
 * that is the order people work in. The first item of each group is its landing
 * page, so a group tab is always clickable.
 */

function isActiveHref(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { context, loading, refresh } = useAuth();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setPendingHref(null);
    setMobileOpen(false);
    setAccountMenuOpen(false);
  }, [pathname]);

  // Same dismiss pattern for the account menu (holds 账户设置 / 关于 / 反馈 / 退出).
  useEffect(() => {
    if (!accountMenuOpen) return;
    function onDown(e: MouseEvent) {
      if (!accountRef.current?.contains(e.target as Node)) setAccountMenuOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setAccountMenuOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [accountMenuOpen]);

  async function onLogout() {
    await logout();
    await refresh();
    router.push("/resume-agent");
  }

  function navClick(e: React.MouseEvent, href: string) {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    if (pathname === href) {
      e.preventDefault();
      return;
    }
    setPendingHref(href);
  }

  const workbench = isWorkbenchPath(pathname);

  return (
    <header className="sticky top-0 z-[10050] border-b border-surface-border bg-surface/85 backdrop-blur-xl backdrop-saturate-150">
      <div
        className={`mx-auto flex h-14 w-full items-center gap-2 sm:gap-3 ${
          workbench ? "max-w-none px-3 sm:px-4" : "max-w-shell px-4"
        }`}
      >
        <Link
          href="/resume-agent"
          className="flex shrink-0 items-center gap-2 text-base font-semibold tracking-tight text-ink-900"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold text-white shadow-brand">
            JC
          </span>
          <span className="hidden sm:inline">舟卡</span>
        </Link>

        {/* Desktop: the three agents first, then the overview they add up to */}
        <nav className="hidden min-w-0 flex-1 items-center gap-1 lg:flex">
          {AGENTS.map((agent) => {
            const active = agentOfPath(pathname)?.id === agent.id;
            return (
              <Link
                key={agent.id}
                href={agent.home}
                prefetch={false}
                onClick={(e) => navClick(e, agent.home)}
                className={`btn btn-sm h-8 gap-2 px-2.5 ${
                  active ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-ink-100 hover:text-ink-900"
                }`}
              >
                <AgentBadge agent={agent} size="sm" />
                {agent.name}
              </Link>
            );
          })}
          <span className="mx-1 h-5 w-px bg-surface-border" aria-hidden />
          <Link
            href={OVERVIEW.href}
            prefetch={false}
            onClick={(e) => navClick(e, OVERVIEW.href)}
            className={`btn btn-sm h-8 px-2.5 ${
              isActiveHref(pathname, OVERVIEW.href)
                ? "bg-brand-50 text-brand-700"
                : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
            }`}
          >
            {OVERVIEW.label}
          </Link>
        </nav>

        {/* Mobile / narrow: single menu button */}
        <button
          type="button"
          aria-expanded={mobileOpen}
          aria-label="打开导航"
          onClick={() => setMobileOpen((v) => !v)}
          className="btn btn-sm btn-ghost ml-auto h-8 w-8 px-0 lg:hidden"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d={mobileOpen ? "M6 18L18 6M6 6l12 12" : "M4 7h16M4 12h16M4 17h16"}
            />
          </svg>
        </button>

        <div className="flex shrink-0 items-center gap-1.5 lg:ml-auto">
          {loading ? (
            <span className="h-7 w-16 animate-pulse rounded-md bg-ink-100" aria-hidden />
          ) : context?.actor === "user" ? (
            <>
              {context.capabilities.includes("admin") ? (
                <Link
                  href="/admin/sessions"
                  className={`btn btn-sm h-8 gap-1 px-2.5 ${
                    pathname.startsWith("/admin")
                      ? "bg-brand-50 text-brand-700"
                      : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
                  }`}
                >
                  管理后台
                </Link>
              ) : null}
              <NotificationCenter />
              <div ref={accountRef} className="relative">
                <button
                  type="button"
                  aria-expanded={accountMenuOpen}
                  aria-haspopup="true"
                  onClick={() => setAccountMenuOpen((v) => !v)}
                  className="btn btn-sm btn-ghost h-8 gap-2 px-1.5 pr-2.5"
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100 text-micro font-semibold text-brand-700">
                    {(context.user?.display_name || context.user?.email || "U").slice(0, 1).toUpperCase()}
                  </span>
                  <span className="hidden max-w-[120px] truncate sm:inline">
                    {context.user?.display_name || "账户"}
                  </span>
                  <svg
                    className={`h-3 w-3 text-ink-400 transition ${accountMenuOpen ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {accountMenuOpen ? (
                  <div className="absolute right-0 top-full z-20 mt-1.5 w-44 animate-scale-in rounded-xl border border-surface-border bg-surface p-1.5 shadow-pop">
                    <Link
                      href="/settings/account"
                      className={`block rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                        pathname === "/settings/account" ? "bg-brand-50 text-brand-700" : "text-ink-800 hover:bg-ink-50"
                      }`}
                    >
                      账户设置
                    </Link>
                    <Link
                      href="/feedback"
                      className={`block rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                        pathname.startsWith("/feedback") ? "bg-brand-50 text-brand-700" : "text-ink-800 hover:bg-ink-50"
                      }`}
                    >
                      反馈
                    </Link>
                    <Link
                      href="/about"
                      className={`block rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                        pathname === "/about" ? "bg-brand-50 text-brand-700" : "text-ink-800 hover:bg-ink-50"
                      }`}
                    >
                      关于
                    </Link>
                    <div className="my-1 border-t border-surface-border" />
                    <button
                      type="button"
                      onClick={onLogout}
                      className="block w-full rounded-lg px-2.5 py-2 text-left text-sm font-medium text-ink-800 transition hover:bg-ink-50"
                    >
                      退出
                    </button>
                  </div>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <Link
                href="/feedback"
                className={`btn btn-sm btn-ghost hidden h-8 px-2.5 sm:inline-flex ${
                  pathname.startsWith("/feedback") ? "bg-brand-50 text-brand-700" : "text-ink-600"
                }`}
              >
                反馈
              </Link>
              <Link
                href="/about"
                className={`btn btn-sm btn-ghost hidden h-8 px-2.5 sm:inline-flex ${
                  pathname === "/about" ? "bg-brand-50 text-brand-700" : "text-ink-600"
                }`}
              >
                关于
              </Link>
              <span className="hidden text-xs text-ink-500 sm:inline">访客</span>
              <Link href="/auth/login" className="btn btn-sm btn-primary h-8">
                登录
              </Link>
            </>
          )}
        </div>
      </div>

      {mobileOpen ? (
        <nav className="animate-fade-in border-t border-surface-border bg-surface px-3 py-2 lg:hidden">
          <div className="py-1">
            <p className="label-meta px-2 py-1">智能体</p>
            <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
              {AGENTS.map((agent) => {
                const active = agentOfPath(pathname)?.id === agent.id;
                return (
                  <Link
                    key={agent.id}
                    href={agent.home}
                    prefetch={false}
                    onClick={(e) => navClick(e, agent.home)}
                    className={`flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                      active ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-ink-50"
                    }`}
                  >
                    <AgentBadge agent={agent} size="sm" />
                    {agent.name}
                  </Link>
                );
              })}
              <Link
                href={OVERVIEW.href}
                prefetch={false}
                onClick={(e) => navClick(e, OVERVIEW.href)}
                className={`rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                  isActiveHref(pathname, OVERVIEW.href)
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-700 hover:bg-ink-50"
                }`}
              >
                {OVERVIEW.label}
              </Link>
            </div>
          </div>
          <div className="py-1">
            <p className="label-meta px-2 py-1">其他</p>
            <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
              <Link
                href="/feedback"
                onClick={(e) => navClick(e, "/feedback")}
                className={`rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                  isActiveHref(pathname, "/feedback")
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-700 hover:bg-ink-50"
                }`}
              >
                反馈
              </Link>
              <Link
                href="/about"
                onClick={(e) => navClick(e, "/about")}
                className={`rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                  pathname === "/about" ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-ink-50"
                }`}
              >
                关于
              </Link>
            </div>
          </div>
          {context?.capabilities.includes("admin") ? (
            <div className="py-1">
              <p className="label-meta px-2 py-1">管理</p>
              <Link
                href="/admin/sessions"
                onClick={(e) => navClick(e, "/admin/sessions")}
                className={`inline-block rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                  pathname.startsWith("/admin")
                    ? "bg-brand-50 text-brand-700"
                    : "text-ink-700 hover:bg-ink-50"
                }`}
              >
                管理后台
              </Link>
            </div>
          ) : null}
        </nav>
      ) : null}

      {pendingHref && pendingHref !== pathname ? (
        <div className="absolute inset-x-0 bottom-0 h-0.5 overflow-hidden bg-brand-100">
          <div className="h-full w-1/3 animate-pulse bg-brand-500" />
        </div>
      ) : null}
    </header>
  );
}
