"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { DimensionRadar } from "@/components/coach/DimensionRadar";
import { getQuestionDetail, type QuestionDetail } from "@/lib/api/coach";

export default function QuestionDetailPage() {
  const params = useParams();
  const questionId = String(params.questionId ?? "");
  const [detail, setDetail] = useState<QuestionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!questionId) return;
    void getQuestionDetail(questionId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [questionId]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (!detail) {
    return <p className="text-sm text-neutral-500">加载中…</p>;
  }

  const latestDims =
    detail.dimension_scores ??
    (detail.attempts[0]?.coach_feedback?.dimensions as Record<string, number> | undefined);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/bank" className="text-sm text-neutral-500 underline">← 题库</Link>
        <h1 className="mt-2 text-xl font-semibold">{detail.stem}</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {detail.company ?? "—"} · {detail.question_type} · {detail.attempt_count} 次练习
          {detail.best_score != null ? ` · 最佳 ${detail.best_score}/10` : ""}
        </p>
        <Link
          href={`/coach-agent?${new URLSearchParams({
            ...(detail.job_id ? { job_id: detail.job_id } : {}),
            practice: detail.id,
          }).toString()}`}
          className="mt-2 inline-block text-sm text-brand-700 underline"
        >
          用这题再练
        </Link>
      </div>

      {latestDims ? (
        <section className="flex flex-col items-start gap-4 rounded-lg border border-neutral-200 p-4 sm:flex-row">
          <DimensionRadar scores={latestDims} />
          <div className="text-sm text-neutral-600">
            <p className="font-medium text-neutral-800">五维评分</p>
            <ul className="mt-2 space-y-1">
              {Object.entries(latestDims).map(([k, v]) => (
                <li key={k}>{k}: {v}/10</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {detail.attempts.length >= 2 ? (
        <section className="rounded-lg border border-brand-100 bg-brand-50/40 p-4">
          <h2 className="font-medium text-slate-900">最近两次对比</h2>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {detail.attempts.slice(0, 2).map((a, idx) => (
              <div key={a.id} className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
                <p className="text-xs text-slate-500">
                  {idx === 0 ? "最近一次" : "上一次"} · {new Date(a.created_at).toLocaleString()}
                  {a.is_best ? " · 最佳" : ""}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-slate-800">{a.user_answer}</p>
                {typeof a.coach_feedback?.score === "number" ? (
                  <p className="mt-2 text-xs text-slate-600">得分 {a.coach_feedback.score}/10</p>
                ) : null}
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section>
        <h2 className="mb-2 font-medium">练习记录</h2>
        <ul className="space-y-4">
          {detail.attempts.map((a) => (
            <li key={a.id} className="rounded-lg border border-neutral-200 p-4 text-sm">
              <div className="flex items-center justify-between text-xs text-neutral-500">
                <span>{new Date(a.created_at).toLocaleString()}</span>
                {a.is_best ? <span className="text-green-700">最佳</span> : null}
              </div>
              <p className="mt-2 whitespace-pre-wrap text-neutral-800">{a.user_answer}</p>
              {a.coach_feedback ? (
                <div className="mt-3 rounded bg-neutral-50 p-3 text-neutral-700">
                  {typeof a.coach_feedback.score === "number" ? (
                    <p className="font-medium">得分 {a.coach_feedback.score}/10</p>
                  ) : null}
                  {Array.isArray(a.coach_feedback.strengths) ? (
                    <p className="mt-1">优点：{(a.coach_feedback.strengths as string[]).join("；")}</p>
                  ) : null}
                  {Array.isArray(a.coach_feedback.gaps) ? (
                    <p className="mt-1">改进：{(a.coach_feedback.gaps as string[]).join("；")}</p>
                  ) : null}
                </div>
              ) : null}
            </li>
          ))}
          {detail.attempts.length === 0 ? (
            <li className="text-neutral-500">暂无练习记录，去模拟面 Agent 答一题。</li>
          ) : null}
        </ul>
      </section>
    </div>
  );
}
