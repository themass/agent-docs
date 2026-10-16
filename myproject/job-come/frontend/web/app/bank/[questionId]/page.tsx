"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DIMENSION_LABELS, DimensionRadar } from "@/components/coach/DimensionRadar";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconChat } from "@/components/ui/Icon";
import { getQuestionDetail, type QuestionDetail } from "@/lib/api/coach";
import { userFacingApiError } from "@/lib/api/user-error";

const TYPE_LABEL: Record<string, string> = {
  behavioral: "行为/STAR",
  project_deep: "项目深挖",
  technical: "技术",
  system_design: "系统设计",
  other: "其他",
};

export default function QuestionDetailPage() {
  const params = useParams();
  const questionId = String(params.questionId ?? "");
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!questionId) return;
    void getQuestionDetail(questionId)
      .then(setDetail)
      .catch((err) => setError(userFacingApiError(err, "加载失败")));
  }, [questionId]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <BackLink />
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <BackLink />
        <div className="card card-pad">
          <div className="skeleton h-5 w-2/3" />
          <div className="skeleton mt-3 h-3 w-48" />
        </div>
      </div>
    );
  }

  const latestDims =
    detail.dimension_scores ??
    (detail.attempts[0]?.coach_feedback?.dimensions as Record<string, number> | undefined);

  const practiceHref = `/coach-agent?${new URLSearchParams({
    ...(detail.job_id ? { job_id: detail.job_id } : {}),
    practice: detail.id,
  }).toString()}`;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-section">
      <BackLink />

      <header className="card bg-sheen card-pad">
        <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
          <div className="min-w-0 max-w-prose">
            <h1 className="text-xl font-semibold leading-snug tracking-tight text-ink-900">
              {detail.stem}
            </h1>
            <p className="mt-2.5 flex flex-wrap items-center gap-1.5">
              {detail.company ? <span className="badge badge-neutral">{detail.company}</span> : null}
              <span className="badge badge-brand">
                {TYPE_LABEL[detail.question_type] ?? detail.question_type}
              </span>
              <span className="text-micro text-ink-500">练习 {detail.attempt_count} 次</span>
              {detail.best_score != null ? (
                <span className="badge badge-success tabular-nums">
                  最佳 {detail.best_score}/10
                </span>
              ) : null}
            </p>
          </div>
          <Link href={practiceHref} className="btn btn-md btn-primary shrink-0">
            用这题再练
            <IconArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </header>

      {latestDims ? (
        <section className="card card-pad">
          <h2 className="text-sm font-semibold text-ink-900">最近一次五维评分</h2>
          <div className="mt-3 flex flex-col items-start gap-5 sm:flex-row sm:items-center">
            <DimensionRadar scores={latestDims} />
            <dl className="min-w-0 flex-1 space-y-2">
              {Object.entries(latestDims).map(([k, v]) => (
                <div key={k} className="flex items-center gap-3">
                  <dt className="w-16 shrink-0 text-xs text-ink-600">{DIMENSION_LABELS[k] ?? k}</dt>
                  <dd className="flex min-w-0 flex-1 items-center gap-2">
                    <span className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-ink-100">
                      <span
                        className="block h-full rounded-full bg-brand-500"
                        style={{ width: `${Math.max(0, Math.min(10, v)) * 10}%` }}
                      />
                    </span>
                    <span className="w-10 shrink-0 text-right text-xs tabular-nums text-ink-700">
                      {v}/10
                    </span>
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      ) : null}

      {detail.attempts.length >= 2 ? (
        <section className="card overflow-hidden">
          <div className="border-b border-surface-border bg-surface-sunken px-4 py-3">
            <h2 className="text-sm font-semibold text-ink-900">最近两次对比</h2>
            <p className="mt-0.5 text-xs text-ink-500">看自己的说法有没有变得更具体</p>
          </div>
          <div className="grid gap-px bg-surface-border md:grid-cols-2">
            {detail.attempts.slice(0, 2).map((a, idx) => (
              <div key={a.id} className="bg-surface p-4">
                <p className="flex flex-wrap items-center gap-1.5">
                  <span className={`badge ${idx === 0 ? "badge-brand" : "badge-neutral"}`}>
                    {idx === 0 ? "最近一次" : "上一次"}
                  </span>
                  {a.is_best ? <span className="badge badge-success">最佳</span> : null}
                  <span className="text-micro text-ink-500">
                    {new Date(a.created_at).toLocaleString("zh-CN")}
                  </span>
                </p>
                <p className="mt-2.5 whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                  {a.user_answer}
                </p>
                {typeof a.coach_feedback?.score === "number" ? (
                  <p className="mt-2.5 text-xs tabular-nums text-ink-600">
                    得分 {a.coach_feedback.score}/10
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-ink-800">练习记录</h2>
        {detail.attempts.length === 0 ? (
          <EmptyState
            compact
            icon={<IconChat />}
            title="还没有练习记录"
            description="去面试辅导页答一遍，这里会留下你的答法和评分。"
            action={
              <Link href={practiceHref} className="btn btn-sm btn-primary">
                现在练一题
              </Link>
            }
          />
        ) : (
          <ul className="space-y-3">
            {detail.attempts.map((a) => (
              <li key={a.id} className="card card-pad">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-micro text-ink-500">
                    {new Date(a.created_at).toLocaleString("zh-CN")}
                  </span>
                  {a.is_best ? <span className="badge badge-success">最佳</span> : null}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-800">
                  {a.user_answer}
                </p>
                {a.coach_feedback ? (
                  <div className="card-sunken mt-3 space-y-1.5 p-3 text-sm text-ink-700">
                    {typeof a.coach_feedback.score === "number" ? (
                      <p className="font-medium tabular-nums text-ink-900">
                        得分 {a.coach_feedback.score}/10
                      </p>
                    ) : null}
                    {Array.isArray(a.coach_feedback.strengths) ? (
                      <p>
                        <span className="text-success-700">优点</span>{" "}
                        {(a.coach_feedback.strengths as string[]).join("；")}
                      </p>
                    ) : null}
                    {Array.isArray(a.coach_feedback.gaps) ? (
                      <p>
                        <span className="text-warn-700">改进</span>{" "}
                        {(a.coach_feedback.gaps as string[]).join("；")}
                      </p>
                    ) : null}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function BackLink() {
  return (
    <Link href="/bank" className="btn btn-sm btn-ghost -ml-2 self-start">
      <svg
        className="h-3.5 w-3.5"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden
      >
        <path d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
      </svg>
      题库
    </Link>
  );
}
