"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { Select } from "@/components/ui/Select";
import { FeedbackStatusBadge } from "@/components/feedback/FeedbackStatusBadge";
import { FeedbackThread } from "@/components/feedback/FeedbackThread";
import {
  addFeedbackMessage,
  createFeedback,
  getFeedback,
  listFeedback,
  type FeedbackCategory,
  type FeedbackThreadDetail,
  type FeedbackThreadItem,
} from "@/lib/api/feedback";
import { useAuth } from "@/lib/auth/AuthProvider";
import { userFacingApiError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";

const CATEGORY_OPTIONS: { value: FeedbackCategory; label: string }[] = [
  { value: "bug", label: "问题反馈" },
  { value: "feature", label: "功能建议" },
  { value: "question", label: "使用咨询" },
  { value: "other", label: "其他" },
];

const CATEGORY_LABEL: Record<FeedbackCategory, string> = {
  bug: "问题反馈",
  feature: "功能建议",
  question: "使用咨询",
  other: "其他",
};

// Small per-category glyph so the list reads as a triaged inbox rather than
// a flat list of identical rows — the same reason the admin side color-codes
// status. Kept to single-path SVGs, no icon library dependency for four glyphs.
const CATEGORY_ICON: Record<FeedbackCategory, { path: string; tone: string }> = {
  bug: { path: "M12 2a5 5 0 00-5 5v1.17A5 5 0 004 13v3a5 5 0 005 5h6a5 5 0 005-5v-3a5 5 0 00-3-4.58V7a5 5 0 00-5-5zm-3 9a1 1 0 112 0v2a1 1 0 11-2 0v-2zm6 0a1 1 0 112 0v2a1 1 0 11-2 0v-2z", tone: "bg-danger-50 text-danger-600" },
  feature: { path: "M12 2a1 1 0 01.894.553l1.382 2.764 3.05.443a1 1 0 01.554 1.705l-2.207 2.15.52 3.038a1 1 0 01-1.451 1.054L12 12.202l-2.742 1.505a1 1 0 01-1.451-1.054l.52-3.038-2.207-2.15a1 1 0 01.554-1.705l3.05-.443 1.382-2.764A1 1 0 0112 2z", tone: "bg-brand-50 text-brand-600" },
  question: { path: "M12 2a10 10 0 100 20 10 10 0 000-20zm.75 14.5h-1.5V15h1.5v1.5zm1.48-6.19c-.32.33-.86.74-1.23 1.08-.3.28-.5.63-.5 1.11h-1.5c0-.86.37-1.44.86-1.92.4-.4.83-.72 1.1-1 .28-.3.44-.6.44-.98 0-.69-.56-1.1-1.4-1.1-.76 0-1.31.37-1.56.96l-1.36-.57C9.5 6.8 10.56 6 12 6c1.6 0 2.9.98 2.9 2.6 0 .78-.33 1.33-.67 1.71z", tone: "bg-warn-50 text-warn-600" },
  other: { path: "M6 10a2 2 0 100 4 2 2 0 000-4zm6 0a2 2 0 100 4 2 2 0 000-4zm6 0a2 2 0 100 4 2 2 0 000-4z", tone: "bg-ink-100 text-ink-500" },
};

function CategoryGlyph({ category }: { category: FeedbackCategory }) {
  const icon = CATEGORY_ICON[category] ?? CATEGORY_ICON.other;
  return (
    <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${icon.tone}`}>
      <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
        <path d={icon.path} />
      </svg>
    </span>
  );
}

function EmptyThreadIllustration() {
  return (
    <div className="m-auto flex max-w-xs flex-col items-center gap-2 px-6 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-ink-100 text-ink-400">
        <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5M21 12c0 4.97-4.03 9-9 9a8.96 8.96 0 01-4.52-1.22L3 21l1.3-3.9A8.96 8.96 0 013 12c0-4.97 4.03-9 9-9s9 4.03 9 9z" />
        </svg>
      </span>
      <p className="text-sm text-ink-500">选择左侧一条反馈查看对话，或新建一条反馈。</p>
    </div>
  );
}

export default function FeedbackPage() {
  const { context, loading: authLoading } = useAuth();
  const [threads, setThreads] = useState<FeedbackThreadItem[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<FeedbackThreadDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [composerOpen, setComposerOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState<FeedbackCategory>("bug");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [replyBody, setReplyBody] = useState("");
  const [replying, setReplying] = useState(false);
  const [replyError, setReplyError] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const res = await listFeedback();
      setThreads(res.threads);
    } catch (e) {
      setListError(userFacingApiError(e, "加载反馈列表失败"));
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    if (context?.actor === "user") void refreshList();
  }, [context?.actor, refreshList]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    setDetailError(null);
    void getFeedback(selectedId)
      .then(setDetail)
      .catch((e) => setDetailError(userFacingApiError(e, "加载反馈详情失败")))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!title.trim() || !body.trim()) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const created = await createFeedback({ title: title.trim(), category, body: body.trim() });
      setTitle("");
      setBody("");
      setCategory("bug");
      setComposerOpen(false);
      await refreshList();
      setSelectedId(created.id);
    } catch (e) {
      setSubmitError(userFacingApiError(e, "提交反馈失败"));
    } finally {
      setSubmitting(false);
    }
  }

  async function onReply(e: FormEvent) {
    e.preventDefault();
    if (!selectedId || !replyBody.trim()) return;
    setReplying(true);
    setReplyError(null);
    try {
      const updated = await addFeedbackMessage(selectedId, replyBody.trim());
      setDetail(updated);
      setReplyBody("");
      await refreshList();
    } catch (e) {
      setReplyError(userFacingApiError(e, "发送留言失败"));
    } finally {
      setReplying(false);
    }
  }

  if (authLoading) return <p className="text-sm text-ink-500">加载中…</p>;
  if (context?.actor !== "user") {
    return (
      <div className="card bg-sheen mx-auto max-w-md px-6 py-10 text-center">
        <p className="text-sm text-ink-600">
          请先{" "}
          <Link className="font-medium text-brand-700 hover:text-brand-800" href="/auth/login">
            登录
          </Link>{" "}
          后提交或查看反馈。
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-1 flex-col gap-4">
      <PageHeader
        eyebrow="反馈"
        title="用户反馈"
        description="遇到 bug、有功能想法，或者单纯想吐槽，都可以在这里告诉我们，我们会在这条对话里直接回复你。"
        actions={
          <button
            type="button"
            className={`btn btn-sm ${composerOpen ? "btn-secondary" : "btn-primary"}`}
            onClick={() => setComposerOpen((v) => !v)}
          >
            {composerOpen ? (
              "取消"
            ) : (
              <>
                <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
                </svg>
                新建反馈
              </>
            )}
          </button>
        }
      />

      {composerOpen ? (
        <form onSubmit={onSubmit} className="card card-pad animate-fade-in space-y-3">
          <div className="grid gap-3 sm:grid-cols-[1fr_11rem]">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="一句话描述问题或建议"
              maxLength={255}
              className="field"
              required
            />
            <Select
              value={category}
              onChange={(e) => setCategory(e.target.value as FeedbackCategory)}
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </Select>
          </div>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder="详细说说发生了什么，或者你希望怎么改进"
            rows={4}
            maxLength={8000}
            className="field resize-none"
            required
          />
          {submitError ? (
            <p className="notice notice-warn text-xs" role="alert">
              {submitError}
            </p>
          ) : null}
          <div className="flex items-center justify-between gap-2">
            <p className="text-micro text-ink-400">提交后会立即出现在左侧列表里，可以继续追加说明。</p>
            <button type="submit" disabled={submitting} className="btn btn-sm btn-primary">
              {submitting ? "提交中…" : "提交反馈"}
            </button>
          </div>
        </form>
      ) : null}

      <div className="grid min-h-0 flex-1 gap-4 sm:grid-cols-[20rem_1fr]">
        <div className="min-h-0 overflow-y-auto rounded-xl border border-surface-border bg-surface">
          {listError ? (
            <p className="notice notice-warn m-3 text-xs" role="alert">
              {listError}
            </p>
          ) : null}
          {listLoading ? (
            <div className="space-y-2 p-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton h-16" />
              ))}
            </div>
          ) : null}
          {!listLoading && threads.length === 0 ? (
            <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-ink-100 text-ink-400">
                <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h8M8 14h5M21 12c0 4.97-4.03 9-9 9a8.96 8.96 0 01-4.52-1.22L3 21l1.3-3.9A8.96 8.96 0 013 12c0-4.97 4.03-9 9-9s9 4.03 9 9z" />
                </svg>
              </span>
              <p className="text-sm text-ink-500">还没有提交过反馈。</p>
              <p className="text-micro text-ink-400">点击右上角「新建反馈」告诉我们你遇到的问题。</p>
            </div>
          ) : null}
          <ul>
            {threads.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(t.id)}
                  className={`flex w-full items-start gap-2.5 border-b border-surface-border px-3 py-3 text-left transition hover:bg-ink-50 ${
                    selectedId === t.id ? "bg-brand-50" : ""
                  }`}
                >
                  <CategoryGlyph category={t.category} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-sm font-medium text-ink-900">{t.title}</p>
                      <FeedbackStatusBadge status={t.status} />
                    </div>
                    <p className="mt-0.5 text-micro text-ink-500">
                      {CATEGORY_LABEL[t.category]} · {t.message_count} 条留言
                    </p>
                    <p className="mt-0.5 text-micro text-ink-400">{formatDateTime(t.last_message_at)}</p>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-surface-border bg-surface">
          {!selectedId ? (
            <EmptyThreadIllustration />
          ) : (
            <>
              <div className="flex shrink-0 items-center justify-between gap-2 border-b border-surface-border px-4 py-3">
                <div className="min-w-0">
                  <h2 className="truncate text-sm font-semibold text-ink-900">{detail?.title ?? ""}</h2>
                  {detail ? (
                    <p className="text-micro text-ink-500">{CATEGORY_LABEL[detail.category]}</p>
                  ) : null}
                </div>
                {detail ? <FeedbackStatusBadge status={detail.status} /> : null}
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto p-4">
                {detailLoading ? (
                  <div className="space-y-3">
                    <div className="skeleton h-14 w-3/4" />
                    <div className="skeleton ml-auto h-10 w-1/2" />
                  </div>
                ) : null}
                {detailError ? (
                  <p className="notice notice-warn text-xs" role="alert">
                    {detailError}
                  </p>
                ) : null}
                {detail && !detailLoading ? (
                  <FeedbackThread messages={detail.messages} viewerRole="user" />
                ) : null}
              </div>
              {detail ? (
                <form onSubmit={onReply} className="shrink-0 border-t border-surface-border p-3">
                  {replyError ? (
                    <p className="notice notice-warn mb-2 text-xs" role="alert">
                      {replyError}
                    </p>
                  ) : null}
                  <div className="flex gap-2">
                    <input
                      value={replyBody}
                      onChange={(e) => setReplyBody(e.target.value)}
                      placeholder="继续补充说明…"
                      className="field flex-1"
                      maxLength={8000}
                    />
                    <button type="submit" disabled={replying || !replyBody.trim()} className="btn btn-sm btn-secondary">
                      {replying ? "发送中…" : "发送"}
                    </button>
                  </div>
                </form>
              ) : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
