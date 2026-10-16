"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconInbox, IconSpark, IconTarget, IconWarn } from "@/components/ui/Icon";
import {
  listJobs,
  parseJob,
  parseJobUrl,
  scoreFit,
  type FitScore,
  type Job,
} from "@/lib/api/jobs";
import { userFacingApiError } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";

const REC_LABEL: Record<string, string> = {
  go: "匹配较好，建议主攻",
  caution: "部分匹配，适合练手并拔高",
  no: "匹配偏低，更适合练手",
};

/** Recommendation drives the badge tone; score alone is too noisy to colour on. */
const REC_BADGE: Record<string, string> = {
  go: "badge badge-success",
  caution: "badge badge-warn",
  no: "badge badge-neutral",
};

type IngestMode = "url" | "text";

export default function JobsPage() {
  const { context } = useAuth();
  const profileId = context?.active_profile_id ?? null;
  const [mode, setMode] = useState<IngestMode>("url");
  const [url, setUrl] = useState("");
  const [dynamicRead, setDynamicRead] = useState(false);
  const [raw, setRaw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [active, setActive] = useState<{ job: Job; fit: FitScore | null } | null>(null);

  useEffect(() => {
    if (!profileId) return;
    void listJobs(profileId).then(setJobs).catch(() => setJobs([]));
  }, [profileId]);

  async function ingest(kind: IngestMode) {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const job =
        kind === "url"
          ? await parseJobUrl(profileId, url.trim(), dynamicRead)
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
      const msg = userFacingApiError(err, "职位解析失败，请稍后重试。");
      setError(
        kind === "url"
          ? `${msg}若链接需要登录或为动态页面，请改粘贴职位描述正文。`
          : msg,
      );
    } finally {
      setBusy(false);
    }
  }

  const canSubmit = mode === "url" ? url.trim().length >= 8 : raw.trim().length >= 20;

  return (
    <div className="mx-auto w-full max-w-4xl space-y-section">
      <EmailVerificationBanner />
      <PageHeader
        eyebrow="行动"
        title="定向岗位"
        description="粘贴招聘链接或职位描述，算出它与当前档案的差距。分数只用来决定主攻还是练手，不会挡住后续的拔高与导出。"
      />

      {!profileId ? (
        <EmptyState
          icon={<IconSpark />}
          title="先建好你的档案"
          description="岗位匹配需要读取一份已确认的档案，否则没有可比对的事实基础。"
          action={
            <Link href="/resume-agent" className="btn btn-md btn-primary">
              去上传简历
              <IconArrowRight className="h-4 w-4" />
            </Link>
          }
        />
      ) : (
        <>
          <section className="card overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-surface-border px-4 py-3 sm:px-5">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-ink-900">添加一个岗位</h2>
                <p className="mt-0.5 text-xs text-ink-500">
                  两种方式结果一致：都会解析成结构化 JD 并立刻打分。
                </p>
              </div>
              <div className="segment">
                <button
                  type="button"
                  onClick={() => setMode("url")}
                  className={`segment-item ${mode === "url" ? "segment-item-active" : ""}`}
                >
                  招聘链接
                </button>
                <button
                  type="button"
                  onClick={() => setMode("text")}
                  className={`segment-item ${mode === "text" ? "segment-item-active" : ""}`}
                >
                  粘贴正文
                </button>
              </div>
            </div>

            <div className="space-y-3 px-4 py-4 sm:px-5">
              {mode === "url" ? (
                <>
                  <input
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    placeholder="https://"
                    className="field"
                    aria-label="招聘链接"
                  />
                  <label className="flex items-start gap-2 text-xs text-ink-600">
                    <input
                      type="checkbox"
                      checked={dynamicRead}
                      disabled={busy}
                      onChange={(event) => setDynamicRead(event.target.checked)}
                      className="mt-0.5 h-3.5 w-3.5 rounded border-surface-border-strong text-brand-600"
                    />
                    <span>
                      动态读取公开页面
                      <span className="text-ink-500">（不登录、不提交，仅只读 GET）</span>
                    </span>
                  </label>
                </>
              ) : (
                <textarea
                  value={raw}
                  onChange={(e) => setRaw(e.target.value)}
                  rows={9}
                  className="field resize-y font-normal"
                  placeholder="把岗位职责、任职要求贴在这里"
                  aria-label="职位描述正文"
                />
              )}

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  disabled={busy || !canSubmit}
                  onClick={() => void ingest(mode)}
                  className="btn btn-md btn-primary"
                >
                  {busy ? (
                    <>
                      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/35 border-t-white" />
                      解析并匹配中…
                    </>
                  ) : (
                    <>
                      <IconTarget className="h-4 w-4" />
                      {mode === "url" ? "抓取 JD 并计算匹配" : "解析正文并计算匹配"}
                    </>
                  )}
                </button>
                {!canSubmit && !busy ? (
                  <span className="text-xs text-ink-500">
                    {mode === "url" ? "请填写完整链接" : "正文至少 20 字"}
                  </span>
                ) : null}
              </div>

              {error ? (
                <p className="notice notice-danger" role="alert">
                  <IconWarn className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </p>
              ) : null}
            </div>
          </section>

          {active ? <FitCard job={active.job} fit={active.fit} /> : null}

          <section className="space-y-3">
            <div className="flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-semibold text-ink-800">已保存岗位</h2>
              {jobs.length ? (
                <span className="text-xs text-ink-500">{jobs.length} 个</span>
              ) : null}
            </div>
            {jobs.length === 0 ? (
              <EmptyState
                compact
                icon={<IconInbox />}
                title="还没有岗位"
                description="解析过的岗位会留在这里，方便按岗反复优化简历。"
              />
            ) : (
              <ul className="space-y-2">
                {jobs.map((job) => (
                  <li key={job.id} className="card card-pad transition hover:shadow-raised">
                    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-ink-900">
                          {job.company} · {job.title}
                        </p>
                        <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-500">
                          {job.fit_score != null ? (
                            <span className="badge badge-neutral tabular-nums">
                              匹配 {job.fit_score}
                            </span>
                          ) : (
                            <span className="badge badge-neutral">尚未打分</span>
                          )}
                          {job.fit_recommendation ? (
                            <span className={REC_BADGE[job.fit_recommendation] ?? "badge badge-neutral"}>
                              {REC_LABEL[job.fit_recommendation] ?? job.fit_recommendation}
                            </span>
                          ) : null}
                        </p>
                      </div>
                      <Link
                        href={`/resume-agent?job_id=${encodeURIComponent(job.id)}`}
                        className="btn btn-sm btn-secondary shrink-0"
                      >
                        按该岗位优化
                        <IconArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    </div>
                    {job.provenance ? (
                      <p className="mt-2.5 break-all border-t border-surface-border pt-2.5 text-micro text-ink-500">
                        来源 {job.provenance.final_url} · {job.provenance.fetched_at} ·{" "}
                        {job.provenance.method === "browser" ? "动态只读" : "静态只读"}
                        <span className="text-ink-500">（网页内容按不可信数据处理）</span>
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}


function FitCard({ job, fit }: { job: Job; fit: FitScore | null }) {
  const rec = fit?.recommendation ?? job.fit_recommendation;
  const score = fit?.score ?? job.fit_score ?? null;
  const hints = fit?.elevate_hints?.length ? fit.elevate_hints : job.elevate_hints ?? [];
  const gaps = fit?.gaps?.length ? fit.gaps : job.fit_gaps;
  const summary = fit?.summary ?? job.fit_summary;

  return (
    <section className="card bg-sheen animate-fade-up overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-surface-border px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <p className="label-meta">刚刚评估</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-ink-900">
            {job.company} · {job.title}
          </h2>
          {rec ? (
            <p className="mt-1.5">
              <span className={REC_BADGE[rec] ?? "badge badge-neutral"}>
                {REC_LABEL[rec] ?? rec}
              </span>
            </p>
          ) : null}
        </div>
        <div className="shrink-0 text-right">
          <p className="label-meta">匹配度</p>
          <p className="text-4xl font-semibold tabular-nums tracking-tight text-brand-700">
            {score ?? "—"}
          </p>
        </div>
      </div>

      <div className="space-y-4 px-4 py-4 sm:px-5">
        {summary ? <p className="max-w-prose text-sm leading-relaxed text-ink-700">{summary}</p> : null}

        {fit?.legitimacy === "suspicious" ? (
          <p className="notice notice-warn">
            <IconWarn className="mt-0.5 h-4 w-4 shrink-0" />
            <span>岗位真实性存疑。这不影响简历拔高，是否投递请自行判断。</span>
          </p>
        ) : null}

        <div className="grid gap-4 sm:grid-cols-2">
          {gaps.length ? (
            <div className="card-sunken card-pad">
              <p className="label-meta">缺口</p>
              <ul className="mt-2 space-y-1.5">
                {gaps.map((g) => (
                  <li key={g} className="flex gap-2 text-sm text-ink-700">
                    <span className="mt-[0.45rem] h-1 w-1 shrink-0 rounded-full bg-warn-600" />
                    <span>{g}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {hints.length ? (
            <div className="card-sunken card-pad">
              <p className="label-meta">可拔高方向</p>
              <p className="mt-1 text-micro text-ink-500">基于你已有的经历改写，不编造</p>
              <ul className="mt-2 space-y-1.5">
                {hints.map((h) => (
                  <li key={h} className="flex gap-2 text-sm text-ink-700">
                    <span className="mt-[0.45rem] h-1 w-1 shrink-0 rounded-full bg-brand-500" />
                    <span>{h}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-1">
          <Link
            href={`/resume-agent?job_id=${encodeURIComponent(job.id)}`}
            className="btn btn-md btn-primary-emphasis"
          >
            按该岗位优化简历
            <IconArrowRight className="h-4 w-4" />
          </Link>
          <p className="text-xs text-ink-500">
            该岗已进入{" "}
            <Link href="/applications" className="font-medium text-brand-700 hover:text-brand-800">
              投递看板
            </Link>{" "}
            的「已评估」。
          </p>
        </div>
      </div>
    </section>
  );
}
