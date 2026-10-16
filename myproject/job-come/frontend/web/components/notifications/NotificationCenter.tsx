"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { resendVerification } from "@/lib/api/auth";
import type { NotificationItem, NotificationPriority } from "@/lib/api/notifications";
import { useNotifications } from "@/lib/notifications/NotificationProvider";

const PRIORITY_STYLES: Record<NotificationPriority, { dot: string; border: string; bg: string }> = {
  critical: { dot: "bg-danger-600", border: "border-danger-200", bg: "bg-danger-50" },
  high: { dot: "bg-warn-600", border: "border-warn-200", bg: "bg-warn-50" },
  normal: { dot: "bg-brand-500", border: "border-brand-200", bg: "bg-brand-50" },
  low: { dot: "bg-ink-400", border: "border-surface-border", bg: "bg-ink-50" },
};

function toneStyle(item: NotificationItem) {
  const tone = item.metadata.tone;
  if (tone === "red") return PRIORITY_STYLES.critical;
  if (tone === "amber") return PRIORITY_STYLES.high;
  if (tone === "rose") return PRIORITY_STYLES.high;
  if (tone === "blue") return PRIORITY_STYLES.normal;
  return PRIORITY_STYLES[item.priority];
}

function formatTime(iso: string) {
  try {
    const d = new Date(iso);
    return d.toLocaleString("zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function NotificationCenter() {
  const { items, unreadCount, loading, refresh, markRead, dismiss } = useNotifications();
  const [open, setOpen] = useState(false);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  async function handleAction(item: NotificationItem) {
    void markRead([item.id]);
    if (item.action?.action === "resend_verification") {
      setActionMsg(null);
      try {
        const res = await resendVerification();
        setActionMsg(res.message);
      } catch (err) {
        setActionMsg(userFacingApiError(err, "发送失败"));
      }
      return;
    }
    if (item.action?.href) {
      setOpen(false);
    }
  }

  return (
    <div className="relative" ref={panelRef}>
      <button
        type="button"
        aria-label="消息通知"
        onClick={() => {
          setOpen((v) => !v);
          if (!open) void refresh();
        }}
        className="btn btn-sm btn-ghost relative h-8 w-8 px-0"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.8}
            d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {unreadCount > 0 ? (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger-600 px-1 text-micro font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-full z-50 mt-2 w-[min(92vw,380px)] animate-scale-in overflow-hidden rounded-xl border border-surface-border bg-surface shadow-pop">
          <div className="flex items-center justify-between border-b border-surface-border px-4 py-3">
            <div>
              <p className="text-sm font-semibold text-ink-900">消息中心</p>
              <p className="text-xs text-ink-500">
                {unreadCount > 0 ? `${unreadCount} 条未读` : "暂无未读"}
              </p>
            </div>
            {items.some((i) => !i.read) ? (
              <button
                type="button"
                onClick={() => void markRead(items.filter((i) => !i.read).map((i) => i.id))}
                className="btn btn-sm btn-ghost text-brand-700 hover:bg-brand-50 hover:text-brand-800"
              >
                全部已读
              </button>
            ) : null}
          </div>

          <div className="max-h-[min(60vh,420px)] overflow-y-auto">
            {loading && !items.length ? (
              <p className="px-4 py-8 text-center text-sm text-ink-500">加载中…</p>
            ) : null}
            {!loading && !items.length ? (
              <p className="px-4 py-10 text-center text-sm text-ink-500">暂无消息</p>
            ) : null}
            <ul className="divide-y divide-surface-border">
              {items.map((item) => {
                const style = toneStyle(item);
                return (
                  <li
                    key={item.id}
                    className={`px-4 py-3 ${!item.read ? style.bg : "bg-surface"}`}
                    onMouseEnter={() => {
                      if (!item.read && item.dismiss_policy === "on_read") {
                        void markRead([item.id]);
                      }
                    }}
                  >
                    <div className="flex gap-3">
                      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className={`text-sm font-medium ${!item.read ? "text-ink-900" : "text-ink-700"}`}>
                            {item.title}
                          </p>
                          <time className="shrink-0 text-micro text-ink-500">{formatTime(item.created_at)}</time>
                        </div>
                        <p className="mt-1 text-xs leading-relaxed text-ink-600">{item.body}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {item.action?.href ? (
                            <Link
                              href={item.action.href}
                              onClick={() => void markRead([item.id])}
                              className="btn btn-sm btn-primary"
                            >
                              {item.action.label}
                            </Link>
                          ) : item.action ? (
                            <button
                              type="button"
                              onClick={() => void handleAction(item)}
                              className="btn btn-sm btn-primary"
                            >
                              {item.action.label}
                            </button>
                          ) : null}
                          {item.dismiss_policy === "manual" ? (
                            <button
                              type="button"
                              onClick={() => void dismiss([item.id])}
                              className="btn btn-sm btn-ghost text-xs"
                            >
                              关闭
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
          {actionMsg ? (
            <p className="border-t border-surface-border px-4 py-2 text-xs text-ink-500">{actionMsg}</p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
