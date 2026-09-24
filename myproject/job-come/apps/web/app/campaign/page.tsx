"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getCampaignStats, tagCampaignJob, type CampaignStats } from "@/lib/api/campaign";
import { listJobs, type Job } from "@/lib/api/jobs";
import { useAuth } from "@/lib/auth/AuthProvider";

const UNLOCK = { interviews: 3, mocks: 5 };

export default function CampaignPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id ?? null;
  const [stats, setStats] = useState<CampaignStats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);

  useEffect(() => {
    if (!profileId) return;
    let cancelled = false;
    setLoadingStats(true);
    setError(null);
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      setError("加载超时，请刷新重试");
      setLoadingStats(false);
    }, 12_000);
    void Promise.all([getCampaignStats(profileId), listJobs(profileId)])
      .then(([nextStats, nextJobs]) => {
        if (cancelled) return;
        window.clearTimeout(timer);
        setStats(nextStats);
        setJobs(nextJobs);
        setLoadingStats(false);
      })
      .catch((err) => {
        if (cancelled) return;
        window.clearTimeout(timer);
        setError(err instanceof Error ? err.message : "加载失败");
        setStats(null);
        setJobs([]);
        setLoadingStats(false);
      });
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [profileId]);

  async function onTag(jobId: string, tag: "warmup" | "target") {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const next = await tagCampaignJob(profileId, jobId, tag);
      setStats(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "标记失败");
    } finally {
      setBusy(false);
    }
  }

  const jobMap = new Map(jobs.map((j) => [j.id, j]));
  const real = stats?.progress.real_interviews ?? 0;
  const mocks = stats?.progress.mock_sessions ?? 0;
  const bank = stats?.progress.bank_question_count ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">战役看板</h1>
        <p className="mt-1 text-sm text-neutral-600">
          练手 → 解锁目标岗 → 定向申请与模拟面（ai-job-search 质量漏斗）
        </p>
      </div>

      {!profileId ? (
        <p className="text-sm text-neutral-600">请先上传简历。</p>
      ) : loadingStats ? (
        <p className="text-sm text-neutral-500">加载中…</p>
      ) : error && !stats ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : !stats ? (
        <p className="text-sm text-neutral-500">暂无看板数据。</p>
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="阶段" value={stats.phase === "target" ? "目标岗" : "练手期"} />
            <StatCard label="真面归档" value={`${real} / ${UNLOCK.interviews}`} />
            <StatCard label="模拟面" value={`${mocks} / ${UNLOCK.mocks}`} />
            <StatCard label="题库" value={String(bank)} />
          </section>

          {stats.phase === "warmup" ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              解锁目标岗：真面 ≥ {UNLOCK.interviews} 且模拟面 ≥ {UNLOCK.mocks}（当前 {real} / {mocks}）
            </p>
          ) : (
            <p className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-900">
              已解锁目标岗阶段，可将岗位标记为 warmup / target。
            </p>
          )}

          <section className="grid gap-6 lg:grid-cols-2">
            <JobBucket
              title="练手岗 (warmup)"
              ids={stats.warmup_job_ids}
              jobMap={jobMap}
              busy={busy}
              onTag={(id) => void onTag(id, "warmup")}
              otherTag="target"
              onMove={(id) => void onTag(id, "target")}
            />
            <JobBucket
              title="目标岗 (target)"
              ids={stats.target_job_ids}
              jobMap={jobMap}
              busy={busy}
              onTag={(id) => void onTag(id, "target")}
              otherTag="warmup"
              onMove={(id) => void onTag(id, "warmup")}
            />
          </section>

          <section>
            <h2 className="mb-2 font-medium">全部岗位</h2>
            <ul className="space-y-2 text-sm">
              {jobs.map((job) => (
                <li key={job.id} className="flex flex-wrap items-center gap-2 rounded border p-3">
                  <span className="flex-1">{job.company} · {job.title}</span>
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded border px-2 py-0.5 text-xs"
                    onClick={() => void onTag(job.id, "warmup")}
                  >
                    练手
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    className="rounded border border-sky-600 px-2 py-0.5 text-xs text-sky-800"
                    onClick={() => void onTag(job.id, "target")}
                  >
                    目标
                  </button>
                  <Link href={`/apply-agent?job_id=${job.id}`} className="text-xs underline">
                    Agent
                  </Link>
                </li>
              ))}
              {jobs.length === 0 ? (
                <li className="text-neutral-500">
                  暂无岗位，去{" "}
                  <Link href="/jobs" className="underline">定向岗位</Link> 添加 JD。
                </li>
              ) : null}
            </ul>
          </section>

          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function JobBucket({
  title,
  ids,
  jobMap,
  busy,
  onTag,
  otherTag,
  onMove,
}: {
  title: string;
  ids: string[];
  jobMap: Map<string, Job>;
  busy: boolean;
  onTag: (id: string) => void;
  otherTag: string;
  onMove: (id: string) => void;
}) {
  return (
    <div className="rounded-lg border border-neutral-200 p-4">
      <h2 className="font-medium">{title}</h2>
      <ul className="mt-3 space-y-2 text-sm">
        {ids.map((id) => {
          const job = jobMap.get(id);
          return (
            <li key={id} className="flex items-center justify-between gap-2">
              <span>{job ? `${job.company} · ${job.title}` : id}</span>
              <button
                type="button"
                disabled={busy}
                className="text-xs underline"
                onClick={() => onMove(id)}
              >
                移到 {otherTag}
              </button>
            </li>
          );
        })}
        {ids.length === 0 ? <li className="text-neutral-500">暂无</li> : null}
      </ul>
    </div>
  );
}
