"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { IconArrowRight, IconBookmark, IconCheck } from "@/components/ui/Icon";
import {
  createMockSession,
  completeMockSession,
  getMockSession,
  getQuestionDetail,
  logQuestion,
  type MockSession,
} from "@/lib/api/coach";
import { listJobs, type Job } from "@/lib/api/jobs";
import { userFacingApiError } from "@/lib/api/user-error";

const TYPES = [
  { id: "behavioral", label: "行为/STAR" },
  { id: "project_deep", label: "项目深挖" },
  { id: "technical", label: "技术" },
  { id: "system_design", label: "系统设计" },
  { id: "other", label: "其他" },
];

const ROUND_GOAL = 3;

type Props = {
  profileId: string | null;
  jobId: string | null;
  practiceQid: string | null;
  disabled: boolean;
  onSessionChange?: (id: string | null) => void;
};

export function CoachFlywheel({ profileId, jobId, practiceQid, disabled, onSessionChange }: Props) {
  const [job, setJob] = useState<Job | null>(null);
  const [mode, setMode] = useState<"warmup" | "target">("warmup");
  const [session, setSession] = useState<MockSession | null>(null);
  const [stem, setStem] = useState("");
  const [qType, setQType] = useState("behavioral");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId || !jobId) {
      setJob(null);
      return;
    }
    void listJobs(profileId)
      .then((jobs) => setJob(jobs.find((j) => j.id === jobId) ?? null))
      .catch(() => setJob(null));
  }, [profileId, jobId]);

  useEffect(() => {
    if (!practiceQid) return;
    void getQuestionDetail(practiceQid)
      .then((d) => setStem(d.stem))
      .catch(() => undefined);
  }, [practiceQid]);

  const logged = session?.questions.length ?? 0;
  const goalHint = useMemo(
    () =>
      logged >= ROUND_GOAL
        ? `本轮已满 ${ROUND_GOAL} 题，可以结束再开一轮抽库`
        : `本轮已记 ${logged} / ${ROUND_GOAL} 题`,
    [logged],
  );

  async function onStart() {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const next = await createMockSession({ profile_id: profileId, mode, job_id: jobId });
      setSession(next);
      onSessionChange?.(next.id);
    } catch (err) {
      setError(userFacingApiError(err, "创建失败"));
    } finally {
      setBusy(false);
    }
  }

  async function onComplete() {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      setSession(await completeMockSession(session.id));
      onSessionChange?.(null);
    } catch (e) {
      setError(userFacingApiError(e, "结束失败"));
    } finally {
      setBusy(false);
    }
  }

  async function onLog() {
    if (!profileId || !session || stem.trim().length < 4) return;
    setBusy(true);
    setError(null);
    try {
      await logQuestion(profileId, {
        stem: stem.trim(),
        question_type: qType,
        company: job?.company ?? null,
        role_title: job?.title ?? null,
        job_id: jobId,
        mock_session_id: session.id,
        user_answer: answer.trim() || null,
      });
      setSession(await getMockSession(session.id));
      setStem("");
      setAnswer("");
    } catch (err) {
      setError(userFacingApiError(err, "记题失败"));
    } finally {
      setBusy(false);
    }
  }

  if (disabled) {
    return (
      <p className="notice notice-warn">
        <span>请登录后开始模拟面试。</span>
      </p>
    );
  }
  if (!profileId) {
    return (
      <div className="card-sunken bg-sheen card-pad">
        <p className="text-sm font-medium text-ink-800">先建好你的档案</p>
        <p className="mt-1 text-sm text-ink-600">模拟面会结合你的真实经历追问，所以需要先有档案。</p>
        <Link href="/resume-agent" className="btn btn-sm btn-primary mt-3">
          去上传简历
          <IconArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
    );
  }

  const active = session?.status === "active";

  return (
    <div className="space-y-4">
      <FlywheelSection
        index={1}
        title="开一轮模拟"
        status={active ? "进行中" : session?.status === "completed" ? "已归档" : undefined}
        statusTone={active ? "brand" : "neutral"}
      >
        <p className="text-sm text-ink-700">
          {job ? (
            <>
              <span className="font-medium text-ink-900">
                {job.company} · {job.title}
              </span>
            </>
          ) : (
            "没有绑定岗位：可以从个人题库练手，或先去定向岗位页选一个 JD。"
          )}
        </p>

        <div className="mt-3">
          <span className="label-meta">模式</span>
          <div className="segment mt-1.5">
            <button
              type="button"
              disabled={active}
              onClick={() => setMode("warmup")}
              className={`segment-item ${mode === "warmup" ? "segment-item-active" : ""}`}
            >
              练手
            </button>
            <button
              type="button"
              disabled={active || !jobId}
              title={!jobId ? "需要先绑定岗位" : undefined}
              onClick={() => setMode("target")}
              className={`segment-item ${mode === "target" ? "segment-item-active" : ""}`}
            >
              目标岗
            </button>
          </div>
          <p className="mt-1.5 text-xs text-ink-500">
            {mode === "warmup"
              ? "节奏放松，给你空间把说法试几遍。"
              : "按这个岗位的真实标准追问，压力更接近现场。"}
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busy || active || (mode === "target" && !jobId)}
            onClick={() => void onStart()}
            className="btn btn-md btn-primary"
          >
            {active ? "本轮进行中" : "开始本轮模拟"}
          </button>
          {active ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => void onComplete()}
              className="btn btn-md btn-secondary"
            >
              结束本轮
            </button>
          ) : null}
        </div>

        {session?.status === "completed" ? (
          <p className="notice notice-success mt-3">
            <IconCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <span>本轮已归档。可以去题库复盘，或再开一轮。</span>
          </p>
        ) : null}
      </FlywheelSection>

      <FlywheelSection
        index={2}
        title="本轮题单"
        status={session ? goalHint : undefined}
        statusTone={logged >= ROUND_GOAL ? "success" : "neutral"}
      >
        <p className="text-xs text-ink-500">
          Agent 会出题；你也可以在下面补记，不依赖模型自觉写库。
        </p>

        {!session ? (
          <p className="card-sunken mt-3 px-3 py-6 text-center text-sm text-ink-500">
            先开始本轮模拟。
          </p>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {session.questions.map((q) => (
                <li key={q.id} className="card-sunken px-3 py-2.5">
                  <p className="text-sm leading-snug text-ink-800">{q.stem}</p>
                  <p className="mt-1.5 flex flex-wrap items-center gap-2">
                    {q.from_bank ? (
                      <span className="badge badge-brand">来自你的题库</span>
                    ) : (
                      <span className="badge badge-neutral">本轮新记</span>
                    )}
                    <Link
                      href={`/bank/${q.id}`}
                      className="text-micro font-medium text-brand-700 hover:text-brand-800"
                    >
                      对比答法
                    </Link>
                  </p>
                </li>
              ))}
              {session.questions.length === 0 ? (
                <li className="card-sunken px-3 py-6 text-center text-sm text-ink-500">
                  还没有题。在右侧开聊，或在下面补记。
                </li>
              ) : null}
            </ul>

            <div className="mt-4 space-y-3 border-t border-surface-border pt-4">
              <label className="block">
                <span className="label-meta">补记题干</span>
                <textarea
                  className="field mt-1.5 resize-y"
                  rows={3}
                  value={stem}
                  onChange={(e) => setStem(e.target.value)}
                  placeholder="把面试官的问题写在这里"
                />
              </label>
              <label className="block">
                <span className="label-meta">题型</span>
                <select
                  className="field mt-1.5"
                  value={qType}
                  onChange={(e) => setQType(e.target.value)}
                >
                  {TYPES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="label-meta">我的回答</span>
                <span className="ml-2 text-micro text-ink-500">可选，会记一版练习</span>
                <textarea
                  className="field mt-1.5 resize-y"
                  rows={3}
                  value={answer}
                  onChange={(e) => setAnswer(e.target.value)}
                />
              </label>
              <button
                type="button"
                disabled={busy || !active || stem.trim().length < 4}
                onClick={() => void onLog()}
                className="btn btn-md btn-secondary"
              >
                记入题库
              </button>
            </div>
          </>
        )}
      </FlywheelSection>

      <FlywheelSection index={3} title="沉淀与再练">
        <p className="text-sm leading-relaxed text-ink-700">
          记满 {ROUND_GOAL} 题后再开一轮，系统会抽一道已入库的题回来，并在题单上标记「来自你的题库」。
        </p>
        <Link
          href={jobId ? `/bank?job_id=${encodeURIComponent(jobId)}` : "/bank"}
          className="btn btn-sm btn-secondary mt-3"
        >
          <IconBookmark className="h-3.5 w-3.5" />
          查看{jobId ? "本岗" : "个人"}题库
        </Link>
      </FlywheelSection>

      {error ? (
        <p className="notice notice-danger" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

function FlywheelSection({
  index,
  title,
  status,
  statusTone = "neutral",
  children,
}: {
  index: number;
  title: string;
  status?: string;
  statusTone?: "neutral" | "brand" | "success";
  children: React.ReactNode;
}) {
  const tone = {
    neutral: "badge badge-neutral",
    brand: "badge badge-brand",
    success: "badge badge-success",
  }[statusTone];
  return (
    <section className="card card-pad">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink-900">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink-100 text-micro font-semibold tabular-nums text-ink-600">
            {index}
          </span>
          {title}
        </h2>
        {status ? <span className={`${tone} shrink-0`}>{status}</span> : null}
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}
