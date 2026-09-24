"use client";

import { useState } from "react";

import { exportProfile, reviewBeforeExport, type ExportReview, type ResumeTrack } from "@/lib/api/resume";

function toExportError(message: string): string {
  if (/no resume draft|no bilingual draft/i.test(message)) {
    return "还没有可导出的优化稿，请先成功生成预览后再审稿/导出。";
  }
  return message;
}

type Props = {
  profileId: string;
  canExport: boolean;
  onExported?: () => void;
  compact?: boolean;
  locale?: ResumeTrack;
  elevationLevel?: "conservative" | "standard" | "elevated";
  draftId?: string | null;
};

export function ExportPanel({
  profileId,
  canExport,
  onExported,
  compact = false,
  locale = "zh-CN",
  elevationLevel = "elevated",
  draftId = null,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [review, setReview] = useState<ExportReview | null>(null);
  const [reviewBusy, setReviewBusy] = useState(false);

  if (!canExport) {
    if (compact) return null;
    return (
      <div className="rounded-2xl border border-surface-border bg-slate-50 p-5 text-sm text-slate-600">
        <p className="font-medium text-slate-800">导出简历</p>
        <p className="mt-1">登录后可导出 PDF / Word，并通过 reviewer 质量检查。</p>
      </div>
    );
  }

  async function runReview() {
    setReviewBusy(true);
    setMessage(null);
    try {
      const res = await reviewBeforeExport(profileId, elevationLevel, locale, draftId);
      setReview(res);
      if (!res.can_export) {
        setMessage(res.notes ?? "审稿未通过，请修改后重试");
      }
    } catch (err) {
            setMessage(err instanceof Error ? toExportError(err.message) : "审稿失败");
    } finally {
      setReviewBusy(false);
    }
  }

  async function runExport(format: "pdf" | "docx") {
    setBusy(true);
    setMessage(null);
    setDownloadUrl(null);
    try {
      if (!review?.can_export) {
        const res = await reviewBeforeExport(profileId, elevationLevel, locale, draftId);
        setReview(res);
        if (!res.can_export) {
          setMessage(res.notes ?? "导出前审稿未通过");
          return;
        }
      }
      const job = await exportProfile(profileId, format, {
        locale,
        elevationLevel,
        draftId: draftId ?? undefined,
      });
      if (job.download_url) {
        setDownloadUrl(job.download_url);
        setMessage("导出成功");
        onExported?.();
      } else {
        setMessage(job.error_message ?? `导出状态：${job.status}`);
      }
    } catch (err) {
      setMessage(err instanceof Error ? toExportError(err.message) : "导出失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={compact ? "" : "rounded-2xl border border-surface-border bg-white p-5 shadow-card sm:p-6"}>
      {!compact ? (
        <>
          <h2 className="text-lg font-semibold text-slate-900">导出与质检</h2>
          <p className="mt-1 text-sm text-slate-500">
            导出前必须通过 resume-reviewer 自动审稿（硬事实、空洞表述、需圆场句子）。
          </p>
        </>
      ) : null}

      <div className={`flex flex-wrap gap-2 ${compact ? "" : "mt-4"}`}>
        <button
          type="button"
          disabled={reviewBusy}
          onClick={() => void runReview()}
          className={`font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 ${
            compact
              ? "rounded-md border border-slate-200 px-2.5 py-1 text-[11px]"
              : "rounded-xl border border-slate-200 px-4 py-2.5 text-sm"
          }`}
        >
          {reviewBusy ? "审稿中…" : compact ? "审稿" : review ? "重新审稿" : "运行审稿"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runExport("pdf")}
          className={`font-medium text-white hover:bg-slate-800 disabled:opacity-50 ${
            compact
              ? "rounded-md bg-slate-900 px-2.5 py-1 text-[11px]"
              : "rounded-xl bg-slate-900 px-4 py-2.5 text-sm"
          }`}
        >
          {locale === "zh-en" ? (compact ? "中英 PDF" : "导出中英对照 PDF") : compact ? "PDF" : "导出 PDF"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void runExport("docx")}
          className={`font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 ${
            compact
              ? "rounded-md border border-surface-border px-2.5 py-1 text-[11px]"
              : "rounded-xl border border-surface-border px-4 py-2.5 text-sm"
          }`}
        >
          {locale === "zh-en" ? (compact ? "中英 Word" : "导出中英对照 Word") : compact ? "Word" : "导出 Word"}
        </button>
      </div>

      {review && !compact ? (
        <div
          className={`mt-3 rounded-lg border px-3 py-2 text-sm ${
            review.can_export
              ? "border-emerald-200 bg-emerald-50 text-emerald-900"
              : "border-amber-200 bg-amber-50 text-amber-900"
          }`}
        >
          <p className="font-medium">
            审稿结果：{review.status === "passed" ? "通过" : "未通过"}
          </p>
          {review.notes ? <p className="mt-1 text-xs">{review.notes}</p> : null}
          {review.issues.length > 0 ? (
            <ul className="mt-2 space-y-1.5">
              {review.issues.map((issue, idx) => {
                const severity = String(issue.severity ?? issue.code ?? "warning");
                const field = issue.field ? String(issue.field) : "";
                const message = String(issue.message ?? issue.code ?? "未通过项");
                return (
                  <li
                    key={`${field}-${idx}`}
                    className="rounded-md bg-white/70 px-2 py-1.5 text-xs text-slate-800"
                  >
                    <span className="font-medium uppercase tracking-wide text-slate-500">
                      {severity}
                    </span>
                    {field ? <span className="ml-1.5 font-mono text-[11px]">{field}</span> : null}
                    <p className="mt-0.5">{message}</p>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
      ) : null}

      {message ? (
        <p className={`${compact ? "mt-1 max-w-[14rem] truncate text-[10px]" : "mt-3 text-sm"} text-slate-600`} title={message}>
          {message}
        </p>
      ) : null}
      {downloadUrl ? (
        <a
          href={downloadUrl}
          className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700"
        >
          点击下载
          <span aria-hidden>→</span>
        </a>
      ) : null}
    </div>
  );
}
