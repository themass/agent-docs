"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconBookmark, IconSpark } from "@/components/ui/Icon";
import { searchBank, type QuestionSummary } from "@/lib/api/coach";
import { userFacingApiError } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";

const TYPE_LABEL: Record<string, string> = {
  behavioral: "行为/STAR",
  project_deep: "项目深挖",
  technical: "技术",
  system_design: "系统设计",
  other: "其他",
};

/** Score colour only at the ends; a 6/10 is not worth a colour. */
function scoreBadge(score: number): string {
  if (score >= 8) return "badge badge-success";
  if (score <= 4) return "badge badge-warn";
  return "badge badge-neutral";
}

function BankInner() {
  const { context } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id;
  const jobId = searchParams.get("job_id");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<QuestionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!profileId) return;
    setLoading(true);
    void searchBank(profileId, { query, job_id: jobId ?? undefined, limit: 30 })
      .then((res) => {
        setItems(res.questions);
        setError(null);
      })
      .catch((err) => setError(userFacingApiError(err, "加载失败")))
      .finally(() => setLoading(false));
  }, [profileId, query, jobId]);

  return (
    <div className="mx-auto w-full max-w-4xl space-y-section">
      <PageHeader
        eyebrow="准备"
        title="面试题库"
        description="每一道练过的题都留在这里，连带你当时的答法和评分。复盘时看的是自己的提升曲线，不是别人的标准答案。"
        actions={
          jobId ? (
            <Link href="/bank" className="btn btn-sm btn-secondary">
              查看全部题目
            </Link>
          ) : null
        }
      />

      {jobId ? (
        <p className="notice notice-info">
          <IconBookmark className="mt-0.5 h-4 w-4 shrink-0" />
          <span>当前只看这个岗位相关的题目。</span>
        </p>
      ) : null}

      {!profileId ? (
        <EmptyState
          icon={<IconSpark />}
          title="先建好你的档案"
          description="题库挂在档案上，这样评分才能结合你的真实经历。"
          action={
            <Link href="/resume-agent" className="btn btn-md btn-primary">
              去上传简历
              <IconArrowRight className="h-4 w-4" />
            </Link>
          }
        />
      ) : (
        <>
          <div className="relative max-w-md">
            <svg
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
              aria-hidden
            >
              <path d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
            </svg>
            <input
              className="field pl-9"
              placeholder="搜索题目或公司"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="搜索题库"
            />
          </div>

          {error ? (
            <p className="notice notice-danger" role="alert">
              {error}
            </p>
          ) : null}

          {loading && items.length === 0 ? (
            <ul className="space-y-2">
              {[0, 1, 2].map((i) => (
                <li key={i} className="card card-pad">
                  <div className="skeleton h-4 w-3/4" />
                  <div className="skeleton mt-2.5 h-3 w-40" />
                </li>
              ))}
            </ul>
          ) : items.length === 0 ? (
            <EmptyState
              icon={<IconBookmark />}
              title={query ? "没有匹配的题目" : "题库还是空的"}
              description={
                query
                  ? "换个关键词，或清空搜索看全部。"
                  : "去面试辅导页开一轮模拟，或者把真实面试里被问到的题补记进来。"
              }
              action={
                query ? (
                  <button type="button" className="btn btn-sm btn-secondary" onClick={() => setQuery("")}>
                    清空搜索
                  </button>
                ) : (
                  <>
                    <Link href="/coach-agent" className="btn btn-sm btn-primary">
                      去模拟面
                    </Link>
                    <Link href="/interviews" className="btn btn-sm btn-secondary">
                      补记真面题目
                    </Link>
                  </>
                )
              }
            />
          ) : (
            <ul className="space-y-2">
              {items.map((q) => (
                <li key={q.id} className="card card-pad transition hover:shadow-raised">
                  <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                    <Link
                      href={`/bank/${q.id}`}
                      className="min-w-0 flex-1 text-sm font-medium leading-snug text-ink-900 hover:text-brand-700"
                    >
                      {q.stem}
                    </Link>
                    <Link
                      href={`/coach-agent?${new URLSearchParams({
                        ...(q.job_id || jobId ? { job_id: q.job_id || jobId || "" } : {}),
                        practice: q.id,
                      }).toString()}`}
                      className="btn btn-sm btn-secondary shrink-0"
                    >
                      用这题再练
                    </Link>
                  </div>
                  <p className="mt-2 flex flex-wrap items-center gap-1.5">
                    {q.company ? <span className="badge badge-neutral">{q.company}</span> : null}
                    <span className="badge badge-brand">
                      {TYPE_LABEL[q.question_type] ?? q.question_type}
                    </span>
                    <span className="text-micro text-ink-500">练习 {q.attempt_count} 次</span>
                    {q.best_score != null ? (
                      <span className={`${scoreBadge(q.best_score)} tabular-nums`}>
                        最佳 {q.best_score}/10
                      </span>
                    ) : null}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}

export default function BankPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-500">加载中…</p>}>
      <BankInner />
    </Suspense>
  );
}
