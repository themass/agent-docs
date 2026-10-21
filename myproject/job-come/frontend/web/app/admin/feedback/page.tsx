"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AdminDrawer } from "@/components/admin/AdminDrawer";
import { FeedbackStatusBadge } from "@/components/feedback/FeedbackStatusBadge";
import { FeedbackThread } from "@/components/feedback/FeedbackThread";
import { nextSortState, SortableTh, type SortState } from "@/components/ui/SortableTh";
import {
  getAdminFeedback,
  listAdminFeedback,
  replyAdminFeedback,
  setAdminFeedbackStatus,
  type AdminFeedbackThreadDetail,
  type AdminFeedbackThreadItem,
} from "@/lib/api/admin";
import type { FeedbackCategory, FeedbackStatus } from "@/lib/api/feedback";
import { formatDateTime } from "@/lib/datetime";
import { userFacingApiError } from "@/lib/api/user-error";

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  bug: "问题反馈",
  feature: "功能建议",
  question: "使用咨询",
  other: "其他",
};

const STATUS_FILTERS: { value: FeedbackStatus | ""; label: string }[] = [
  { value: "", label: "全部" },
  { value: "open", label: "待处理" },
  { value: "replying", label: "已回复" },
  { value: "resolved", label: "已解决" },
  { value: "closed", label: "已关闭" },
];

const STATUS_ACTIONS: { value: FeedbackStatus; label: string }[] = [
  { value: "resolved", label: "标记已解决" },
  { value: "closed", label: "关闭" },
  { value: "open", label: "重新打开" },
];

export default function AdminFeedbackPage() {
  const [threads, setThreads] = useState<AdminFeedbackThreadItem[]>([]);
  const [total, setTotal] = useState(0);
  const [statusFilter, setStatusFilter] = useState<FeedbackStatus | "">("");
  const [sort, setSort] = useState<SortState>({ sortBy: "last_message_at", sortDir: "desc" });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminFeedbackThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [replyBody, setReplyBody] = useState("");
  const [replying, setReplying] = useState(false);
  const [statusActionBusy, setStatusActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadThreads = useCallback(
    async (status: FeedbackStatus | "", order: SortState) => {
      setLoading(true);
      setError(null);
      try {
        const res = await listAdminFeedback({
          limit: 100,
          status: status || undefined,
          sort_by: order.sortBy,
          sort_dir: order.sortDir,
        });
        setThreads(res.threads);
        setTotal(res.total);
        setSort({ sortBy: res.sort_by, sortDir: res.sort_dir });
      } catch (e) {
        setError(userFacingApiError(e, "加载反馈列表失败"));
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadThreads(statusFilter, sort);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, loadThreads, sort.sortBy, sort.sortDir]);

  function onSort(columnKey: string) {
    const textFirstAsc = ["title", "category", "status", "user_id", "last_message_role"].includes(columnKey);
    setSort((cur) => nextSortState(cur, columnKey, textFirstAsc ? "asc" : "desc"));
  }

  const loadDetail = useCallback((threadId: string) => {
    setDetailLoading(true);
    setDetailError(null);
    void getAdminFeedback(threadId)
      .then(setDetail)
      .catch((e) => setDetailError(userFacingApiError(e, "加载反馈详情失败")))
      .finally(() => setDetailLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    loadDetail(selectedId);
  }, [selectedId, loadDetail]);

  async function onReply(e: FormEvent) {
    e.preventDefault();
    if (!selectedId || !replyBody.trim()) return;
    setReplying(true);
    setActionError(null);
    try {
      const updated = await replyAdminFeedback(selectedId, replyBody.trim());
      setDetail(updated);
      setReplyBody("");
      await loadThreads(statusFilter, sort);
    } catch (e) {
      setActionError(userFacingApiError(e, "回复失败"));
    } finally {
      setReplying(false);
    }
  }

  async function onSetStatus(status: FeedbackStatus) {
    if (!selectedId) return;
    setStatusActionBusy(true);
    setActionError(null);
    try {
      const updated = await setAdminFeedbackStatus(selectedId, status);
      setDetail(updated);
      await loadThreads(statusFilter, sort);
    } catch (e) {
      setActionError(userFacingApiError(e, "更新状态失败"));
    } finally {
      setStatusActionBusy(false);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
      <div className="flex shrink-0 flex-wrap items-center gap-3">
        <div>
          <h1 className="text-sm font-semibold text-ink-900">用户反馈</h1>
          <p className="text-xs text-ink-500">{loading ? "加载中…" : `共 ${total} 条反馈`}</p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value || "all"}
              type="button"
              onClick={() => setStatusFilter(f.value)}
              className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                statusFilter === f.value
                  ? "bg-brand-50 text-brand-700"
                  : "text-ink-600 hover:bg-ink-100 hover:text-ink-900"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {error ? (
        <p className="notice notice-warn shrink-0 text-xs" role="alert">
          {error}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-surface-border bg-surface shadow-card">
        <table className="w-full border-collapse text-sm">
          <thead className="sticky top-0 z-10 bg-surface-sunken text-xs text-ink-500">
            <tr>
              <SortableTh columnKey="title" label="标题" sort={sort} onSort={onSort} />
              <SortableTh columnKey="user_id" label="用户" sort={sort} onSort={onSort} />
              <SortableTh columnKey="category" label="分类" sort={sort} onSort={onSort} />
              <SortableTh columnKey="status" label="状态" sort={sort} onSort={onSort} />
              <SortableTh columnKey="message_count" label="消息数" sort={sort} onSort={onSort} align="right" />
              <SortableTh columnKey="last_message_at" label="最后更新" sort={sort} onSort={onSort} />
            </tr>
          </thead>
          <tbody>
            {threads.map((t) => (
              <tr
                key={t.id}
                onClick={() => setSelectedId(t.id)}
                className="cursor-pointer border-t border-surface-border transition hover:bg-ink-50"
              >
                <td className="max-w-[20rem] truncate px-3 py-2 text-ink-900">{t.title}</td>
                <td className="px-3 py-2 text-ink-700">
                  {t.user_display_name || t.user_email}
                </td>
                <td className="px-3 py-2 text-ink-700">{CATEGORY_LABEL[t.category]}</td>
                <td className="px-3 py-2">
                  <FeedbackStatusBadge status={t.status} />
                </td>
                <td className="px-3 py-2 text-right font-mono text-xs text-ink-700">
                  {t.message_count}
                </td>
                <td className="px-3 py-2 text-xs text-ink-500">{formatDateTime(t.last_message_at)}</td>
              </tr>
            ))}
            {!loading && threads.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-sm text-ink-500">
                  没有匹配的反馈
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>

      <AdminDrawer
        open={selectedId !== null}
        onClose={() => setSelectedId(null)}
        title={detail?.title ?? selectedId ?? ""}
        subtitle={
          detail ? `${detail.user_display_name || detail.user_email} · ${detail.id}` : undefined
        }
        defaultWidth={576}
      >
        {detailLoading ? <p className="text-sm text-ink-500">加载中…</p> : null}
        {detailError ? (
          <p className="notice notice-warn text-xs" role="alert">
            {detailError}
          </p>
        ) : null}
        {detail && !detailLoading ? (
          <div className="flex h-full min-h-0 flex-col gap-3">
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <FeedbackStatusBadge status={detail.status} />
              <span className="text-xs text-ink-500">{CATEGORY_LABEL[detail.category]}</span>
              <div className="ml-auto flex gap-1.5">
                {STATUS_ACTIONS.filter((a) => a.value !== detail.status).map((a) => (
                  <button
                    key={a.value}
                    type="button"
                    disabled={statusActionBusy}
                    onClick={() => onSetStatus(a.value)}
                    className="btn btn-sm btn-ghost text-xs"
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            </div>

            {actionError ? (
              <p className="notice notice-warn shrink-0 text-xs" role="alert">
                {actionError}
              </p>
            ) : null}

            <div className="min-h-0 flex-1 overflow-y-auto">
              <FeedbackThread
                messages={detail.messages}
                viewerRole="admin"
                userLabel={detail.user_display_name || detail.user_email}
              />
            </div>

            <form onSubmit={onReply} className="shrink-0 border-t border-surface-border pt-3">
              <textarea
                value={replyBody}
                onChange={(e) => setReplyBody(e.target.value)}
                placeholder="回复用户…"
                rows={3}
                maxLength={8000}
                className="field resize-none"
              />
              <div className="mt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={replying || !replyBody.trim()}
                  className="btn btn-sm btn-primary"
                >
                  {replying ? "发送中…" : "发送回复"}
                </button>
              </div>
            </form>
          </div>
        ) : null}
      </AdminDrawer>
    </div>
  );
}
