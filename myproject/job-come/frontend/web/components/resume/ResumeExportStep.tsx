"use client";

import { useEffect, useState } from "react";

import { MembershipDialog } from "@/components/membership/MembershipDialog";
import { ApiError } from "@/lib/api/errors";
import { getMembership, type Membership } from "@/lib/api/membership";
import {
  exportProfile,
  type ExportFormat,
  type ResumeTrack,
} from "@/lib/api/resume";
import { userFacingExportError } from "@/lib/api/user-error";
import { formatDateTime } from "@/lib/datetime";
import type { ResumeQualityReview } from "@/lib/hooks/useResumeQualityReview";
import { ExportReviewProgress } from "./ExportReviewProgress";

type Props = {
  quality: ResumeQualityReview;
  profileId: string;
  canExport: boolean;
  locale: ResumeTrack;
  elevationLevel: "conservative" | "standard" | "elevated";
  draftId: string | null;
  onExported?: () => void;
  onBackToElevate?: () => void;
};

type FormatCard = {
  id: ExportFormat;
  label: string;
  tagline: string;
  detail: string;
  primary?: boolean;
};

const FORMATS: FormatCard[] = [
  {
    id: "pdf",
    label: "PDF",
    tagline: "投递首选",
    detail: "排版固定，任何设备打开都一致。绝大多数招聘系统接受。",
    primary: true,
  },
  {
    id: "docx",
    label: "Word",
    tagline: "需要改动时用",
    detail: "可继续编辑。部分猎头和内推人会要求 Word 版本。",
  },
  {
    id: "html",
    label: "网页版",
    tagline: "在线分享",
    detail: "单个 HTML 文件，可直接发送或挂到个人主页，手机上也好读。",
  },
];

const TRACK_LABEL: Record<ResumeTrack, string> = {
  "zh-CN": "中文简历",
  "en-US": "英文简历",
  "zh-en": "中英对照",
};

const LEVEL_LABEL: Record<Props["elevationLevel"], string> = {
  conservative: "保守",
  standard: "标准",
  elevated: "强化",
};

type DoneFile = { format: ExportFormat; url: string };

/**
 * Step 4. Reuse the optimization verdict and download; never launch a second check.
 * No content editing here; wording changes belong to step 3.
 */
export function ResumeExportStep({
  quality,
  profileId,
  canExport,
  locale,
  elevationLevel,
  draftId,
  onExported,
  onBackToElevate,
}: Props) {
  const { review, reviewBusy, reviewError, acknowledged, skipped, skipReview, setAcknowledged } = quality;
  const [busyFormat, setBusyFormat] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [downloadNotice, setDownloadNotice] = useState<string | null>(null);
  const [files, setFiles] = useState<DoneFile[]>([]);
  const [membership, setMembership] = useState<Membership | null>(null);
  const [quotaDialogOpen, setQuotaDialogOpen] = useState(false);
  useEffect(() => {
    setFiles([]);
    setExportError(null);
  }, [profileId, locale, elevationLevel, draftId]);
  useEffect(() => {
    if (canExport) void refreshMembership();
  }, [canExport]);

  async function refreshMembership() {
    try {
      setMembership(await getMembership());
    } catch {
      setMembership(null);
    }
  }

  async function runExport(format: ExportFormat) {
    // The free download is a single lifetime allowance: make the user choose before it is spent.
    if (membership?.free_download_available && membership.tier !== "admin") {
      const formatName = format === "pdf" ? "PDF" : format === "docx" ? "Word" : "网页版";
      if (!window.confirm(`这会用掉你唯一一次免费下载机会（终身一次）。\n\n生成${formatName}并成功下载后计入；之后下载需要开通会员。\n\n确定现在下载吗？`)) {
        return;
      }
    }
    setBusyFormat(format);
    setExportError(null);
    setDownloadNotice(null);
    try {
      const job = await exportProfile(profileId, format, {
        locale,
        elevationLevel,
        draftId: draftId ?? undefined,
      });
      if (job.download_url) {
        setFiles((prev) => [
          { format, url: job.download_url as string },
          ...prev.filter((f) => f.format !== format),
        ]);
        onExported?.();
        setDownloadNotice(`${format === "pdf" ? "PDF" : format === "docx" ? "Word" : "网页版"}已生成，文件在下方可以下载。`);
        void refreshMembership();
      } else {
        setExportError(job.error_message ?? `导出未完成（状态：${job.status}）`);
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === "download_quota_exhausted") {
        setQuotaDialogOpen(true);
        void refreshMembership();
      } else {
        setExportError(userFacingExportError(err));
      }
    } finally {
      setBusyFormat(null);
    }
  }

  if (!canExport) {
    return (
      <div className="card bg-sheen px-6 py-12 text-center">
        <p className="text-base font-semibold text-ink-900">登录后可导出简历</p>
        <p className="mx-auto mt-1.5 max-w-prose text-sm leading-relaxed text-ink-500">
          导出需要账号，以便保存你的简历版本和下载记录。
        </p>
      </div>
    );
  }

  if (!draftId) {
    return (
      <div className="card bg-sheen px-6 py-12 text-center">
        <p className="text-base font-semibold text-ink-900">还没有可导出的简历</p>
        <p className="mx-auto mt-1.5 max-w-prose text-sm leading-relaxed text-ink-500">
          请先回到「优化预览」生成一份优化稿。
        </p>
        <button type="button" onClick={onBackToElevate} className="btn btn-md btn-primary mt-5">
          返回优化预览
        </button>
      </div>
    );
  }

  const errors = (review?.issues ?? []).filter(
    (i) => String(i.severity ?? i.code ?? "error").toLowerCase() !== "warning",
  );
  // What this file *is*, as opposed to how good it reads. These two need no model, so
  // they are shown even when the reviewer produced no verdict -- an unavailable
  // reviewer is precisely when "the writer never ran" would otherwise go unmentioned,
  // and a failed optimization downloads under the same filename as a successful one.
  const DELIVERY_CODES = ["generation_not_optimized", "placeholder_bullet"];
  const deliveryIssues = (review?.issues ?? []).filter((i) =>
    DELIVERY_CODES.includes(String(i.code ?? "")),
  );
  const unavailable = review?.status === "unavailable" || review?.reviewed === false || reviewError != null;
  // A delivery finding keeps this out of "直接选择格式下载": the headline must not say the
  // document is fine while a warning underneath says the AI writer never ran.
  const clean =
    review != null && !unavailable && errors.length === 0 && deliveryIssues.length === 0;
  const needsAck = !unavailable && errors.length > 0 && !acknowledged;
  const settled = !reviewBusy || review != null || reviewError != null || skipped;
  const downloadable = settled && !needsAck;

  return (
    <div className="space-y-3">
      {/* What exactly is about to leave the building. */}
      <section className="card card-pad">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-ink-900">即将导出</h2>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <span className="badge badge-neutral">{TRACK_LABEL[locale]}</span>
              <span className="badge badge-brand">{LEVEL_LABEL[elevationLevel]}档优化稿</span>
            </div>
          </div>
          <button type="button" onClick={onBackToElevate} className="btn btn-sm btn-secondary">
            修改内容
          </button>
        </div>
      </section>

      <section className="card card-pad" aria-live="polite">
        <h2 className="text-sm font-semibold text-ink-900">优化页内容检查结果</h2>
        <p className="mt-2 text-xs leading-relaxed text-ink-600">
          {reviewBusy ? "优化页启动的检查仍在进行，无需重复检查。" :
            clean ? "已完成内容检查，直接选择格式下载。" :
            unavailable || skipped ? "内容检查未完成，不代表检查通过；仍可下载。" :
            errors.length ? `有 ${errors.length} 处内容待确认，可查看下面的问题后继续下载。` :
            "尚未完成内容检查，可返回优化页查看或直接下载。"}
        </p>
        {reviewBusy && !review ? (
          <ExportReviewProgress
            progress={quality.reviewProgress}
            startedAt={quality.reviewStartedAt}
            busy={reviewBusy}
          />
        ) : null}
        {deliveryIssues.length > 0 ? (
          <div className="notice notice-warn mt-2" role="status">
            <ul className="space-y-1 text-xs leading-relaxed">
              {deliveryIssues.map((issue, i) => <li key={i}>{issue.message}</li>)}
            </ul>
          </div>
        ) : null}
        {errors.length > 0 && !unavailable ? (
          <ul className="mt-2 space-y-1 text-xs text-warn-700">
            {errors.map((issue, i) => <li key={i}>{issue.message}</li>)}
          </ul>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={onBackToElevate} className="btn btn-sm btn-secondary">查看优化与检查详情</button>
          {reviewBusy ? <button type="button" onClick={skipReview} className="btn btn-sm btn-ghost">停止等待，直接下载</button> : null}
          {needsAck ? <button type="button" onClick={() => setAcknowledged(true)} className="btn btn-sm btn-ghost">我已了解，继续下载</button> : null}
        </div>
      </section>

      {/* Download. Only ever waits on the user reading the findings -- never on the
          check succeeding. An unavailable reviewer leaves this fully enabled. */}
      {membership ? (
        <DownloadQuotaNotice membership={membership} onUpgrade={() => setQuotaDialogOpen(true)} />
      ) : null}
      <section className={`card card-pad transition ${downloadable ? "" : "opacity-60"}`}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink-900">选择格式下载</h2>
          {needsAck ? (
            <span className="badge badge-warn">先看一下上面的 {errors.length} 处问题</span>
          ) : !settled ? (
            <span className="badge badge-neutral">质检进行中，可跳过等待</span>
          ) : (
            <span className="text-xs text-ink-500">三种格式内容完全一致</span>
          )}
        </div>

        <div className="mt-3.5 grid gap-2.5 sm:grid-cols-3">
          {FORMATS.map((fmt) => {
            const done = files.find((f) => f.format === fmt.id);
            const busy = busyFormat === fmt.id;
            return (
              <div
                key={fmt.id}
                className={`flex flex-col rounded-xl p-3.5 ring-1 ring-inset transition ${
                  done
                    ? "bg-success-50/50 ring-success-200"
                    : fmt.primary && downloadable
                      ? "bg-brand-50/40 ring-brand-200"
                      : "bg-surface-sunken ring-surface-border"
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-base font-semibold text-ink-900">{fmt.label}</span>
                  <span className="label-meta">{fmt.tagline}</span>
                </div>
                <p className="mt-1.5 min-h-[3rem] text-xs leading-relaxed text-ink-600">
                  {fmt.detail}
                </p>
                {done ? (
                  <a href={done.url} className="btn btn-sm btn-success mt-2.5">
                    下载 {fmt.label}
                    <span aria-hidden>↓</span>
                  </a>
                ) : (
                  <button
                    type="button"
                    disabled={!downloadable || busyFormat !== null}
                    onClick={() => void runExport(fmt.id)}
                    className={`btn btn-sm mt-2.5 ${fmt.primary ? "btn-primary" : "btn-secondary"}`}
                  >
                    {busy ? (
                      <>
                        <svg viewBox="0 0 24 24" aria-hidden="true" className="h-3.5 w-3.5 animate-spin" fill="none">
                          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
                          <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
                        </svg>
                        生成中…
                      </>
                    ) : (
                      `生成 ${fmt.label}`
                    )}
                  </button>
                )}
              </div>
            );
          })}
        </div>

        {downloadNotice ? (
          <div className="notice notice-success mt-3.5 text-sm" role="status">
            <span>{downloadNotice}</span>
          </div>
        ) : null}
        {exportError ? (
          <div className="notice notice-danger mt-3.5 text-sm" role="alert">
            <span>{exportError}</span>
          </div>
        ) : null}

        {files.length > 0 ? (
          <p className="mt-3.5 text-xs text-ink-500">
            已生成 {files.length} 个文件。重新优化内容后需要再次导出才会更新。
          </p>
        ) : null}
      </section>

      <MembershipDialog
        open={quotaDialogOpen}
        reason="quota_exhausted"
        onClose={() => setQuotaDialogOpen(false)}
        onMembershipChanged={setMembership}
      />
    </div>
  );
}

function DownloadQuotaNotice({
  membership,
  onUpgrade,
}: {
  membership: Membership;
  onUpgrade: () => void;
}) {
  if (membership.tier === "admin") return null;
  if (membership.tier === "vip") {
    return (
      <p className="text-xs text-ink-600">
        会员有效期至 {formatDateTime(membership.vip_expires_at)}，下载不限次数。
      </p>
    );
  }
  if (membership.free_download_available) {
    return (
      <div className="notice notice-info mb-3 text-sm" role="status">
        <p className="font-semibold">你有 1 次免费下载机会（终身一次）</p>
        <p className="mt-1 text-xs">下载成功后计入，之后需要开通会员才能继续下载。开通会员后不限次数。</p>
      </div>
    );
  }
  return (
    <div className="notice notice-warn flex flex-wrap items-center justify-between gap-2 text-xs" role="status">
      <span>免费下载次数已用完。开通会员后可以不限次数下载。</span>
      <button type="button" onClick={onUpgrade} className="btn btn-sm btn-primary">
        开通会员
      </button>
    </div>
  );
}
