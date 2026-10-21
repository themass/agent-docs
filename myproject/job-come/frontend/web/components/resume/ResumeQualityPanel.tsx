"use client";

import type { ResumeQualityReview } from "@/lib/hooks/useResumeQualityReview";
import { ExportReviewProgress } from "./ExportReviewProgress";

type Props = {
  quality: ResumeQualityReview;
  onRegenerate: () => void;
  onEditProfile: () => void;
};

/** Content feedback belongs beside the draft, before format selection. */
export function ResumeQualityPanel({ quality, onRegenerate, onEditProfile }: Props) {
  const { review, reviewBusy, reviewError, acknowledged, skipped, reviewProgress,
    reviewStartedAt, runReview, skipReview, setAcknowledged } = quality;
  const errors = (review?.issues ?? []).filter(
    (i) => String(i.severity ?? i.code ?? "error").toLowerCase() !== "warning",
  );
  const warnings = (review?.issues ?? []).filter(
    (i) => String(i.severity ?? i.code ?? "error").toLowerCase() === "warning",
  );
  // Three outcomes, and only one of them is a statement about the resume.
  //
  // `unavailable` means the check could not run (gateway down, model off, unreadable
  // response). The user neither caused it nor can fix it, so it is reported as "not
  // checked" rather than as a problem with their document.
  // A request that never came back is the same situation as a reviewer that could not
  // reach a verdict, so the two are handled as one state.
  const unavailable =
    review?.status === "unavailable" || review?.reviewed === false || reviewError != null;
  const clean = review != null && !unavailable && errors.length === 0;
  const diag = review?.diagnostics ?? null;
  const keywords = diag?.keyword_coverage;
  const cov = review?.coverage ?? null;
  // Only worth showing when something is actually missing; a full-coverage draft needs
  // no reassurance panel competing with the download buttons.
  const showCoverage = Boolean(cov && (cov.projects_missing || cov.dropped.length > 0));

  return (
    <div className="space-y-3">
      {/* Content review starts beside the newly generated draft. */}
      <section className="card card-pad" aria-live="polite">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink-900">优化稿内容检查</h2>
          {review || reviewError || skipped ? (
            <button
              type="button"
              onClick={() => void runReview()}
              disabled={reviewBusy}
              className="btn btn-sm btn-ghost text-brand-700 hover:text-brand-800"
            >
              {reviewBusy ? "检查中…" : "重新检查"}
            </button>
          ) : null}
        </div>
        <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
          生成后自动核对经历、数字和成果。有问题就在这里处理，不必等到导出再折返。
          检查不会自动改写事实或覆盖内容；重新生成后会检查新稿。
        </p>

        <div className="mt-2 flex flex-wrap gap-2">
          <button type="button" onClick={onEditProfile} className="btn btn-sm btn-secondary">修改档案事实</button>
          <button type="button" onClick={onRegenerate} className="btn btn-sm btn-secondary">重新生成优化稿</button>
        </div>

        {/* Progress is driven by server stages, never by elapsed time. */}
        {reviewBusy && !review ? (
          <ExportReviewProgress
            progress={reviewProgress}
            startedAt={reviewStartedAt}
            busy={reviewBusy}
            onSkip={skipReview}
          />
        ) : null}

        {/* An unreachable endpoint says nothing about the resume, so it is not an
            alert. Same copy family as the server-side `unavailable` verdict. */}
        {reviewError ? (
          <div className="notice notice-warn mt-3">
            <span aria-hidden className="mt-px shrink-0">ℹ</span>
            <div className="min-w-0">
              <p className="font-medium">这次没检查成功，不影响下载</p>
              <p className="mt-0.5 text-xs leading-relaxed opacity-80">
                {reviewError}可以重新检查，也可以直接下载——质检只是帮你复核，不是下载的前置条件。
              </p>
            </div>
          </div>
        ) : null}

        {skipped && !review && !reviewError ? (
          <p className="mt-3 text-xs leading-relaxed text-ink-500">
            已停止本次检查，可以继续导出。本次未完成的核对不会显示为通过。
          </p>
        ) : null}

        {review ? (
          <>
            <div
              className={`notice mt-3 ${
                clean ? "notice-success" : unavailable ? "notice-info" : "notice-warn"
              }`}
            >
              <span
                aria-hidden
                className={`mt-px inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-micro font-bold text-white ${
                  clean ? "bg-success-600" : unavailable ? "bg-ink-400" : "bg-warn-600"
                }`}
              >
                {clean ? "✓" : unavailable ? "i" : "!"}
              </span>
              <div className="min-w-0">
                <p className="font-medium">
                  {clean
                    ? "内容检查通过"
                    : unavailable
                      ? "这次没有完成检查，不影响下载"
                      : `发现 ${errors.length} 处建议先确认的问题`}
                </p>
                {review.notes ? (
                  <p className="mt-0.5 text-xs leading-relaxed opacity-80">{review.notes}</p>
                ) : null}
                {unavailable ? (
                  <p className="mt-0.5 text-xs leading-relaxed opacity-80">
                    自动复核没能完成，这不代表简历有问题。你可以重新检查，也可以直接下载。
                  </p>
                ) : null}
              </div>
            </div>

            {/* Issues the reviewer raised about the draft. When the reviewer never ran,
                the only entries are internal diagnostics (`reviewer_unavailable` and
                friends) in English, which would read as defects in the resume. The
                notice above already explains the situation. */}
            {!unavailable && errors.length > 0 ? (
              <div className="mt-3.5">
                <p className="text-xs font-semibold text-danger-700">
                  建议先确认（{errors.length}）
                </p>
                <ul className="mt-2 space-y-1.5">
                  {errors.map((issue, idx) => (
                    <li
                      key={`err-${idx}`}
                      className="rounded-lg bg-danger-50/60 px-3 py-2 ring-1 ring-inset ring-danger-100"
                    >
                      {issue.field ? (
                        <span className="font-mono text-micro text-ink-500">{issue.field}</span>
                      ) : null}
                      <p className="mt-0.5 text-xs leading-relaxed text-ink-800">
                        {issue.message ?? issue.code ?? "未通过项"}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {!unavailable && warnings.length > 0 ? (
              <div className="mt-3.5">
                <p className="text-xs font-semibold text-warn-700">
                  建议优化（{warnings.length}）· 不影响导出
                </p>
                <ul className="mt-2 space-y-1.5">
                  {warnings.map((issue, idx) => (
                    <li
                      key={`warn-${idx}`}
                      className="rounded-lg bg-warn-50/50 px-3 py-2 ring-1 ring-inset ring-warn-100"
                    >
                      {issue.field ? (
                        <span className="font-mono text-micro text-ink-500">{issue.field}</span>
                      ) : null}
                      <p className="mt-0.5 text-xs leading-relaxed text-ink-800">
                        {issue.message ?? issue.code ?? "建议项"}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* Two real options, both offered. Going back is the better one, which is
                why it leads -- but "download anyway" exists, because the findings can
                be wrong (merging two highlights legitimately breaks attribution) and
                only the user knows which. Acknowledging is one click, not a modal:
                the point is that the findings were seen, not that leaving is hard. */}
            {!unavailable && errors.length > 0 ? (
              <div className="mt-3.5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={onRegenerate}
                  className="btn btn-sm btn-primary"
                >
                  重新生成优化稿
                </button>
                {acknowledged ? (
                  <span className="text-xs text-ink-500">已确认，可以继续导出。</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setAcknowledged(true)}
                    className="btn btn-sm btn-ghost text-ink-600"
                  >
                    我已了解，继续导出
                  </button>
                )}
              </div>
            ) : null}
          </>
        ) : null}
      </section>

      {/* Screening readiness: measured, not judged. Separate from the honesty gate
          because "will a recruiter read this" and "is this true" are different
          questions, and only the second one may block a download. */}
      {diag ? (
        <section className="card card-pad">
          <h2 className="text-sm font-semibold text-ink-900">篇幅与投递建议</h2>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            这些是机器可以直接数出来的指标，不影响导出，但很影响简历会不会被读完。
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <div className="card-sunken px-3 py-2.5">
              <dt className="label-meta">估算篇幅</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink-900">
                约 {diag.estimated_pages} 页
              </dd>
            </div>
            <div className="card-sunken px-3 py-2.5">
              <dt className="label-meta">要点条数</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink-900">{diag.bullet_count} 条</dd>
            </div>
            <div className="card-sunken px-3 py-2.5">
              <dt className="label-meta">最长要点</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink-900">
                {diag.longest_bullet_chars} 字
              </dd>
            </div>
            <div className="card-sunken px-3 py-2.5">
              <dt className="label-meta">岗位用词覆盖</dt>
              <dd className="mt-0.5 text-sm font-semibold text-ink-900">
                {keywords && keywords.total > 0
                  ? `${keywords.present}/${keywords.total}`
                  : "未选岗位"}
              </dd>
            </div>
          </dl>
          {diag.notes.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {diag.notes.map((note, idx) => (
                <li
                  key={`diag-${idx}`}
                  className="rounded-lg bg-ink-50 px-3 py-2 text-xs leading-relaxed text-ink-700"
                >
                  {note}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-xs text-ink-500">篇幅、要点长度和岗位用词覆盖都没有明显问题。</p>
          )}
        </section>
      ) : null}

      {/* Content coverage. "Did the document keep my career" is the complaint users
          actually voice, and it is neither an honesty question nor a layout one, so it
          gets its own block. Advisory: merging duplicate highlights is legitimate. */}
      {showCoverage && cov ? (
        <section className="card card-pad">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink-900">经历覆盖度</h2>
            <span className="badge badge-warn">
              {cov.covered}/{cov.source_highlights} 条已写入
            </span>
          </div>
          <p className="mt-1 max-w-prose text-xs leading-relaxed text-ink-500">
            下面这些档案里的内容没有出现在简历中。如果是重复表述可以忽略；
            如果是重要经历，在本页重新生成一次。
          </p>
          {cov.projects_missing ? (
            <div className="notice notice-warn mt-3">
              <span className="text-xs">
                档案里有项目经历，但这份简历没有项目这一节。建议重新生成优化稿。
              </span>
            </div>
          ) : null}
          {cov.dropped.length > 0 ? (
            <ul className="mt-3 space-y-1.5">
              {cov.dropped.slice(0, 6).map((item, idx) => (
                <li key={`drop-${idx}`} className="card-sunken px-3 py-2">
                  <span className="label-meta">{item.where}</span>
                  <p className="mt-0.5 text-xs leading-relaxed text-ink-700">{item.text}</p>
                </li>
              ))}
            </ul>
          ) : null}
          {cov.dropped.length > 6 ? (
            <p className="mt-2 text-xs text-ink-500">
              另有 {cov.dropped.length - 6} 条未列出。
            </p>
          ) : null}
          <button
            type="button"
            onClick={onRegenerate}
            className="btn btn-sm btn-secondary mt-3"
          >
            返回重新生成
          </button>
        </section>
      ) : null}

    </div>
  );
}
