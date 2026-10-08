"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { searchBank, type QuestionSummary } from "@/lib/api/coach";
import { useAuth } from "@/lib/auth/AuthProvider";

function BankInner() {
  const { context } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id;
  const jobId = searchParams.get("job_id");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<QuestionSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId) return;
    void searchBank(profileId, { query, job_id: jobId ?? undefined, limit: 30 })
      .then((res) => setItems(res.questions))
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [profileId, query, jobId]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">面试题库</h1>
      {jobId ? (
        <p className="text-sm text-slate-600">
          仅看本岗题目。{" "}
          <Link href="/bank" className="underline">
            查看全部
          </Link>
        </p>
      ) : null}
      {!profileId ? (
        <p className="text-sm text-neutral-600">请先上传简历创建档案。</p>
      ) : (
        <>
          <input
            className="w-full max-w-md rounded border border-neutral-300 px-3 py-2 text-sm"
            placeholder="搜索题目或公司"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <ul className="space-y-3">
            {items.map((q) => (
              <li key={q.id} className="rounded border border-neutral-200 p-3 text-sm">
                <Link href={`/bank/${q.id}`} className="font-medium hover:underline">
                  {q.stem}
                </Link>
                <p className="mt-1 text-neutral-500">
                  {q.company ?? "—"} · {q.question_type} · 练习 {q.attempt_count} 次
                  {q.best_score != null ? ` · 最佳 ${q.best_score}/10` : ""}
                </p>
                <Link
                  href={`/coach-agent?${new URLSearchParams({
                    ...(q.job_id || jobId ? { job_id: q.job_id || jobId || "" } : {}),
                    practice: q.id,
                  }).toString()}`}
                  className="mt-1 inline-block text-xs text-brand-700 underline"
                >
                  用这题再练
                </Link>
              </li>
            ))}
            {items.length === 0 ? (
              <li className="text-sm text-neutral-500">暂无题目，请在面试辅导页补记或让 Agent 出题。</li>
            ) : null}
          </ul>
        </>
      )}
    </div>
  );
}

export default function BankPage() {
  return (
    <Suspense fallback={<p className="text-sm text-neutral-500">加载中…</p>}>
      <BankInner />
    </Suspense>
  );
}
