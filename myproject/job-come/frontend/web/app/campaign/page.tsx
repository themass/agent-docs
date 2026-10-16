"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconCheck, IconSpark, IconTarget } from "@/components/ui/Icon";
import { StatTile } from "@/components/ui/StatTile";
import { getCampaignStats, tagCampaignJob, type CampaignStats } from "@/lib/api/campaign";
import { listJobs, type Job } from "@/lib/api/jobs";
import { userFacingApiError } from "@/lib/api/user-error";
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
        setError(userFacingApiError(err, "加载失败"));
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
      setError(userFacingApiError(err, "标记失败"));
    } finally {
      setBusy(false);
    }
  }

  const jobMap = new Map(jobs.map((j) => [j.id, j]));
  const real = stats?.progress.real_interviews ?? 0;
  const mocks = stats?.progress.mock_sessions ?? 0;
  const bank = stats?.progress.bank_question_count ?? 0;
  const unlocked = stats?.phase === "target";

  return (
    <div className="space-y-section">
      <PageHeader
        eyebrow="复盘"
        title="战役看板"
        description="一轮主动跳槽的节奏：先在练手岗上把答法打磨顺，再把精力压到真正想去的目标岗。"
      />

      {!profileId ? (
        <EmptyState
          icon={<IconSpark />}
          title="先建好你的档案"
          description="看板上的进度都挂在某一份档案上。"
          action={
            <Link href="/resume-agent" className="btn btn-md btn-primary">
              去上传简历
              <IconArrowRight className="h-4 w-4" />
            </Link>
          }
        />
      ) : loadingStats ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="card p-4">
              <div className="skeleton h-3 w-16" />
              <div className="skeleton mt-3 h-7 w-20" />
            </div>
          ))}
        </div>
      ) : error && !stats ? (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      ) : !stats ? (
        <EmptyState compact title="暂无看板数据" />
      ) : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="当前阶段"
              value={unlocked ? "目标岗" : "练手期"}
              tone={unlocked ? "success" : "brand"}
              hint={unlocked ? "可以主攻了" : "先把节奏练顺"}
            />
            <StatTile
              label="真面归档"
              value={
                <>
                  {real}
                  <span className="text-lg font-normal text-ink-500"> / {UNLOCK.interviews}</span>
                </>
              }
            />
            <StatTile
              label="模拟面"
              value={
                <>
                  {mocks}
                  <span className="text-lg font-normal text-ink-500"> / {UNLOCK.mocks}</span>
                </>
              }
            />
            <StatTile label="题库沉淀" value={bank} hint="道已记录的题目" />
          </section>

          {unlocked ? (
            <p className="notice notice-success">
              <IconCheck className="mt-0.5 h-4 w-4 shrink-0" />
              <span>已进入目标岗阶段。现在可以把岗位分到「练手」和「目标」两桶里分配精力。</span>
            </p>
          ) : (
            <section className="card card-pad">
              <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
                <div>
                  <p className="text-sm font-medium text-ink-900">解锁目标岗阶段</p>
                  <p className="mt-0.5 text-xs text-ink-500">
                    真面归档 ≥ {UNLOCK.interviews} 且模拟面 ≥ {UNLOCK.mocks}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Link href="/coach-agent" className="btn btn-sm btn-primary">
                    去模拟面
                  </Link>
                  <Link href="/interviews" className="btn btn-sm btn-secondary">
                    归档真面
                  </Link>
                </div>
              </div>
              <div className="mt-4 space-y-3">
                <UnlockBar label="真面归档" value={real} total={UNLOCK.interviews} />
                <UnlockBar label="模拟面" value={mocks} total={UNLOCK.mocks} />
              </div>
            </section>
          )}

          <section className="grid gap-4 lg:grid-cols-2">
            <JobBucket
              title="练手岗"
              hint="用来打磨答法，压力小、容错高"
              ids={stats.warmup_job_ids}
              jobMap={jobMap}
              busy={busy}
              moveLabel="移到目标岗"
              onMove={(id) => void onTag(id, "target")}
            />
            <JobBucket
              title="目标岗"
              hint="真正想去的地方，值得单独准备"
              accent
              ids={stats.target_job_ids}
              jobMap={jobMap}
              busy={busy}
              moveLabel="移到练手岗"
              onMove={(id) => void onTag(id, "warmup")}
            />
          </section>

          <section className="space-y-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink-800">全部岗位</h2>
              {jobs.length ? <span className="text-xs text-ink-500">{jobs.length} 个</span> : null}
            </div>
            {jobs.length === 0 ? (
              <EmptyState
                compact
                icon={<IconTarget />}
                title="还没有岗位"
                description="先去定向岗位页解析一份 JD，它就会出现在这里。"
                action={
                  <Link href="/jobs" className="btn btn-sm btn-primary">
                    去添加 JD
                  </Link>
                }
              />
            ) : (
              <ul className="space-y-2">
                {jobs.map((job) => {
                  const inWarmup = stats.warmup_job_ids.includes(job.id);
                  const inTarget = stats.target_job_ids.includes(job.id);
                  return (
                    <li
                      key={job.id}
                      className="card flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3"
                    >
                      <span className="min-w-0 flex-1 truncate text-sm font-medium text-ink-900">
                        {job.company} · {job.title}
                      </span>
                      <div className="segment">
                        <button
                          type="button"
                          disabled={busy}
                          className={`segment-item ${inWarmup ? "segment-item-active" : ""}`}
                          onClick={() => void onTag(job.id, "warmup")}
                        >
                          练手
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          className={`segment-item ${inTarget ? "segment-item-active" : ""}`}
                          onClick={() => void onTag(job.id, "target")}
                        >
                          目标
                        </button>
                      </div>
                      <Link
                        href={`/apply-agent?job_id=${encodeURIComponent(job.id)}`}
                        className="btn btn-sm btn-ghost shrink-0"
                      >
                        定向申请
                        <IconArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {error ? (
            <p className="notice notice-danger" role="alert">
              {error}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}

function UnlockBar({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = Math.min(100, Math.round((value / total) * 100));
  const done = value >= total;
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-ink-600">{label}</span>
        <span className={`tabular-nums ${done ? "text-success-700" : "text-ink-500"}`}>
          {value} / {total}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-100">
        <div
          className={`h-full rounded-full transition-[width] duration-slow ${done ? "bg-success-600" : "bg-brand-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function JobBucket({
  title,
  hint,
  ids,
  jobMap,
  busy,
  moveLabel,
  onMove,
  accent = false,
}: {
  title: string;
  hint: string;
  ids: string[];
  jobMap: Map<string, Job>;
  busy: boolean;
  moveLabel: string;
  onMove: (id: string) => void;
  accent?: boolean;
}) {
  return (
    <div className="card overflow-hidden">
      <div
        className={`flex items-start justify-between gap-3 border-b border-surface-border px-4 py-3 ${
          accent ? "bg-brand-50/60" : "bg-surface-sunken"
        }`}
      >
        <div className="min-w-0">
          <h2 className={`text-sm font-semibold ${accent ? "text-brand-800" : "text-ink-900"}`}>
            {title}
          </h2>
          <p className="mt-0.5 text-xs text-ink-500">{hint}</p>
        </div>
        <span className="badge badge-neutral shrink-0 tabular-nums">{ids.length}</span>
      </div>
      <ul className="divide-y divide-surface-border">
        {ids.map((id) => {
          const job = jobMap.get(id);
          return (
            <li key={id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="min-w-0 flex-1 truncate text-sm text-ink-800">
                {job ? `${job.company} · ${job.title}` : id}
              </span>
              <button
                type="button"
                disabled={busy}
                className="btn btn-sm btn-ghost shrink-0"
                onClick={() => onMove(id)}
              >
                {moveLabel}
              </button>
            </li>
          );
        })}
        {ids.length === 0 ? (
          <li className="px-4 py-6 text-center text-xs text-ink-500">暂无</li>
        ) : null}
      </ul>
    </div>
  );
}
