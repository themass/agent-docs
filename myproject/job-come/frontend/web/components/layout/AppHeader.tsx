"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { logout } from "@/lib/api/auth";
import { useAuth } from "@/lib/auth/AuthProvider";
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
type NavItem = { href: string; label: string; desc: string };
type NavGroup = { id: string; label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    id: "prepare",
    label: "准备",
    items: [
      { href: "/resume-agent", label: "简历优化", desc: "优化简历并导出投递版本" },
      { href: "/coach-agent", label: "面试辅导", desc: "针对岗位练习问答" },
      { href: "/bank", label: "题库", desc: "沉淀下来的问题与答案" },
    ],
  },
  {
    id: "act",
    label: "行动",
    items: [
      { href: "/jobs", label: "定向岗位", desc: "解析 JD 并看匹配与差距" },
      { href: "/apply-agent", label: "定向申请", desc: "按岗位准备申请材料" },
      { href: "/applications", label: "投递看板", desc: "自己维护的机会漏斗" },
    ],
  },
  {
    id: "track",
    label: "复盘",
    items: [
      { href: "/campaign", label: "战役看板", desc: "这一轮跳槽的整体节奏" },
      { href: "/interviews", label: "面试归档", desc: "真实面试记录与复盘" },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function isActiveHref(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppHeader() {
  const router = useRouter();
  const pathname = usePathname();
  const { context, loading, refresh } = useAuth();
  const [pendingHref, setPendingHref] = useState<string | null>(null);
  const [openGroup, setOpenGroup] = useState<string | null>(null);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    setPendingHref(null);
    setOpenGroup(null);
    setMobileOpen(false);
  }, [pathname]);

  // Dismiss the group menu on outside click or Escape so it never traps focus.
  useEffect(() => {
    if (!openGroup) return;
    function onDown(e: MouseEvent) {
      if (!navRef.current?.contains(e.target as Node)) setOpenGroup(null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpenGroup(null);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [openGroup]);

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

  const activeItem = ALL_ITEMS.find((i) => isActiveHref(pathname, i.href));

  return (
    <header className="sticky top-0 z-[10050] border-b border-surface-border bg-surface/85 backdrop-blur-xl backdrop-saturate-150">
      <div className="mx-auto flex h-14 max-w-shell items-center gap-2 px-4 sm:gap-3">
        <Link
          href="/resume-agent"
          className="flex shrink-0 items-center gap-2 text-base font-semibold tracking-tight text-ink-900"
        >
          <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600 text-xs font-bold text-white shadow-brand">
            JC
          </span>
          <span className="hidden sm:inline">舟卡</span>
        </Link>

        {/* Desktop: grouped navigation */}
        <nav ref={navRef} className="hidden min-w-0 flex-1 items-center gap-0.5 lg:flex">
          {NAV_GROUPS.map((group) => {
            const groupActive = group.items.some((i) => isActiveHref(pathname, i.href));
            const open = openGroup === group.id;
            return (
              <div key={group.id} className="relative">
                <button
                  type="button"
                  aria-expanded={open}
                  aria-haspopup="true"
                  onClick={() => setOpenGroup(open ? null : group.id)}
                  className={`btn btn-sm h-8 gap-1 px-2.5 ${
                    groupActive
                      ? "bg-brand-50 text-brand-700"
                      : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
                  }`}
                >
                  {group.label}
                  {groupActive && activeItem ? (
                    <span className="hidden text-ink-300 xl:inline" aria-hidden>
                      /
                    </span>
                  ) : null}
                  {groupActive && activeItem ? (
                    <span className="hidden font-semibold xl:inline">{activeItem.label}</span>
                  ) : null}
                  <svg
                    className={`h-3 w-3 text-ink-400 transition ${open ? "rotate-180" : ""}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    aria-hidden
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {open ? (
                  <div className="absolute left-0 top-full z-20 mt-1.5 w-72 animate-scale-in rounded-xl border border-surface-border bg-surface p-1.5 shadow-pop">
                    {group.items.map((item) => {
                      const active = isActiveHref(pathname, item.href);
                      return (
                        <Link
                          key={item.href}
                          href={item.href}
                          prefetch={false}
                          onClick={(e) => navClick(e, item.href)}
                          className={`block rounded-lg px-2.5 py-2 transition ${
                            active ? "bg-brand-50" : "hover:bg-ink-50"
                          }`}
                        >
                          <span
                            className={`block text-sm font-medium ${
                              active ? "text-brand-700" : "text-ink-800"
                            }`}
                          >
                            {item.label}
                          </span>
                          <span className="mt-0.5 block text-xs text-ink-500">{item.desc}</span>
                        </Link>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
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
              <NotificationCenter />
              <Link
                href="/settings/account"
                className="btn btn-sm btn-ghost h-8 gap-2 px-1.5 pr-2.5"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-brand-100 text-micro font-semibold text-brand-700">
                  {(context.user?.display_name || context.user?.email || "U").slice(0, 1).toUpperCase()}
                </span>
                <span className="hidden max-w-[120px] truncate sm:inline">
                  {context.user?.display_name || "账户"}
                </span>
              </Link>
              <button type="button" onClick={onLogout} className="btn btn-sm btn-ghost h-8">
                退出
              </button>
            </>
          ) : (
            <>
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
          {NAV_GROUPS.map((group) => (
            <div key={group.id} className="py-1">
              <p className="label-meta px-2 py-1">{group.label}</p>
              <div className="grid grid-cols-2 gap-1 sm:grid-cols-3">
                {group.items.map((item) => {
                  const active = isActiveHref(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      prefetch={false}
                      onClick={(e) => navClick(e, item.href)}
                      className={`rounded-lg px-2.5 py-2 text-sm font-medium transition ${
                        active ? "bg-brand-50 text-brand-700" : "text-ink-700 hover:bg-ink-50"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
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
