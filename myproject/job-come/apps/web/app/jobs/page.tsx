"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import {
  listJobs,
  parseJob,
  parseJobUrl,
  scoreFit,
  type FitScore,
  type Job,
} from "@/lib/api/jobs";
import { useAuth } from "@/lib/auth/AuthProvider";

const REC_LABEL: Record<string, string> = {
  go: "匹配较好，建议主攻",
  caution: "部分匹配，适合练手并拔高",
  no: "匹配偏低，更适合练手",
};

export default function JobsPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id ?? null;
  const [url, setUrl] = useState("");
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<{ job: Job; fit: FitScore | null } | null>(null);

  useEffect(() => {
    if (!profileId) return;
    void listJobs(profileId).then(setJobs).catch(() => setJobs([]));
  }, [profileId]);

  async function ingest(kind: "url" | "text") {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const job =
        kind === "url"
          ? await parseJobUrl(profileId, url.trim())
          : await parseJob(profileId, raw.trim());
      const fit = await scoreFit(profileId, job.id);
      const merged: Job = {
        ...job,
        fit_score: fit.score,
        fit_recommendation: fit.recommendation,
        fit_gaps: fit.gaps,
        fit_blockers: fit.blockers,
        fit_summary: fit.summary,
        elevate_hints: fit.elevate_hints,
        fit_dimensions: fit.dimensions,
        legitimacy: fit.legitimacy,
      };
      setActive({ job: merged, fit });
      setJobs((prev) => [merged, ...prev.filter((j) => j.id !== merged.id)]);
    } catch (err) {
      setError(
        err instanceof Error
          ? kind === "url"
            ? `${err.message}。若页面需登录或为前端渲染，请改粘贴职位描述正文。`
            : err.message
          : "解析失败",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <EmailVerificationBanner />
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">定向岗位</h1>
        <p className="mt-1 text-sm text-slate-600">
          粘贴招聘链接或职位描述，计算与当前档案的匹配度。无论分数高低，都可以按该岗位优化简历。
        </p>
      </div>

      {!profileId ? (
        <p className="text-sm text-slate-600">
          请先在{" "}
          <Link href="/resume-agent" className="text-brand-700 underline">
            简历优化
          </Link>{" "}
          上传档案。
        </p>
      ) : (
        <>
          <section className="space-y-3 rounded-2xl border border-surface-border bg-white p-4 shadow-card">
            <label className="block text-sm font-medium text-slate-800">粘贴招聘链接</label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={busy || url.trim().length < 8}
              onClick={() => void ingest("url")}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? "抓取并匹配中…" : "抓取 JD 并计算匹配"}
            </button>

            <div className="border-t border-slate-100 pt-3">
              <label className="block text-sm font-medium text-slate-800">或粘贴职位描述</label>
              <textarea
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                rows={8}
                className="mt-2 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                placeholder="把岗位职责、任职要求贴在这里"
              />
              <button
                type="button"
                disabled={busy || raw.trim().length < 20}
                onClick={() => void ingest("text")}
                className="mt-2 rounded-lg border border-slate-200 px-4 py-2 text-sm disabled:opacity-50"
              >
                解析正文并计算匹配
              </button>
            </div>
            {error ? <p className="text-sm text-red-600">{error}</p> : null}
          </section>

          {active ? <FitCard job={active.job} fit={active.fit} /> : null}

          <section>
            <h2 className="mb-2 text-sm font-semibold text-slate-800">已保存岗位</h2>
            <ul className="space-y-2">
              {jobs.map((job) => (
                <li key={job.id} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
                  <p className="font-medium">
                    {job.company} · {job.title}
                    {job.fit_score != null ? (
                      <span className="ml-2 text-slate-500">匹配 {job.fit_score}</span>
                    ) : null}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {job.fit_recommendation
                      ? REC_LABEL[job.fit_recommendation] ?? job.fit_recommendation
                      : "尚未打分"}
                  </p>
                  <Link
                    href={`/resume-agent?job_id=${encodeURIComponent(job.id)}`}
                    className="mt-2 inline-block text-brand-700 underline"
                  >
                    按该岗位优化简历
                  </Link>
                </li>
              ))}
              {jobs.length === 0 ? <li className="text-sm text-slate-500">还没有岗位。</li> : null}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}

function FitCard({ job, fit }: { job: Job; fit: FitScore | null }) {
  const rec = fit?.recommendation ?? job.fit_recommendation;
  const hints = fit?.elevate_hints?.length ? fit.elevate_hints : job.elevate_hints ?? [];
  return (
    <section className="space-y-3 rounded-2xl border border-brand-100 bg-brand-50/40 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-900">
          {job.company} · {job.title}
        </h2>
        <p className="text-sm text-slate-600">
          匹配度 {fit?.score ?? job.fit_score ?? "—"}
          {rec ? ` · ${REC_LABEL[rec] ?? rec}` : ""}
        </p>
      </div>
      {fit?.summary || job.fit_summary ? (
        <p className="text-sm text-slate-700">{fit?.summary ?? job.fit_summary}</p>
      ) : null}
      {fit?.legitimacy === "suspicious" ? (
        <p className="text-xs text-amber-800">岗位真实性存疑（不影响拔高，请自行判断是否投递）。</p>
      ) : null}
      {(fit?.gaps.length || job.fit_gaps.length) ? (
        <div>
          <p className="text-xs font-medium text-slate-500">缺口</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
            {(fit?.gaps ?? job.fit_gaps).map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {hints.length ? (
        <div>
          <p className="text-xs font-medium text-slate-500">可拔高方向（不编造经历）</p>
          <ul className="mt-1 list-disc pl-5 text-sm text-slate-700">
            {hints.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <Link
        href={`/resume-agent?job_id=${encodeURIComponent(job.id)}`}
        className="inline-flex rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        按该岗位优化简历
      </Link>
    </section>
  );
}
