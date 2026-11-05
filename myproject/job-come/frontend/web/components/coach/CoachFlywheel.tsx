"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { IconArrowRight, IconBookmark, IconCheck } from "@/components/ui/Icon";
import { Select } from "@/components/ui/Select";
import {
  createMockSession,
  completeMockSession,
  getActiveMockSession,
  getLevelRecommendation,
  getMockSession,
  getQuestionDetail,
  logQuestion,
  type LevelRecommendation,
  type MockKind,
  type MockLevel,
  type MockSession,
  type MockStyle,
} from "@/lib/api/coach";
import { MockProgress } from "@/components/coach/MockProgress";
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

const KIND_OPTIONS: { id: MockKind; label: string; hint: string }[] = [
  { id: "warmup", label: "热身 5 题", hint: "不限次数，适合先试几遍说法。" },
  { id: "full", label: "完整模拟 20 题", hint: "免费账号每月 1 场，报告独立给出。" },
];

const STYLE_OPTIONS: { id: MockStyle; label: string; hint: string }[] = [
  { id: "gentle", label: "温和引导", hint: "先给思路时间，追问偏鼓励。" },
  { id: "standard", label: "标准", hint: "按真实面试节奏追问。" },
  { id: "pressure", label: "压力", hint: "直接指出模糊和对不上的地方。" },
  { id: "deep", label: "业务深挖", hint: "每题追到取舍和结果怎么衡量。" },
];

type Props = {
  profileId: string | null;
  jobId: string | null;
  practiceQid: string | null;
  disabled: boolean;
  onSessionChange?: (id: string | null) => void;
  onJobChange?: (id: string | null) => void;
  /** The round is open on the server; the page asks the interviewer to open the first question. */
  onStarted?: (session: MockSession) => void;
};

export function CoachFlywheel({
  profileId,
  jobId,
  practiceQid,
  disabled,
  onSessionChange,
  onJobChange,
  onStarted,
}: Props) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [kind, setKind] = useState<MockKind>("warmup");
  const [style, setStyle] = useState<MockStyle>("standard");
  // The recommendation comes from the profile; the choice is the user's. The first fills the
  // second only while the user has not chosen, so a slow answer never overrides a click.
  const [recommendation, setRecommendation] = useState<LevelRecommendation | null>(null);
  const [recommendationFailed, setRecommendationFailed] = useState(false);
  const [level, setLevel] = useState<MockLevel | null>(null);
  const [session, setSession] = useState<MockSession | null>(null);
  const [stem, setStem] = useState("");
  const [qType, setQType] = useState("behavioral");
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [finishedId, setFinishedId] = useState<string | null>(null);

  useEffect(() => {
    if (!profileId) {
      setJobs([]);
      return;
    }
    void listJobs(profileId)
      .then(setJobs)
      .catch(() => setJobs([]));
  }, [profileId]);

  useEffect(() => {
    // A different profile has a different recommendation, and a level filled in from the old one
    // does not carry over. The user's own pick is theirs, but it was a pick for that profile too.
    setRecommendation(null);
    setLevel(null);
    if (!profileId) return;
    let cancelled = false;
    setRecommendationFailed(false);
    void getLevelRecommendation(profileId)
      .then((result) => {
        if (cancelled) return;
        setRecommendation(result);
        setLevel((chosen) => chosen ?? result.recommended);
      })
      .catch(() => {
        if (!cancelled) setRecommendationFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [profileId]);

  // The interview id lives on the server. After a reload this page remembers nothing, so it asks
  // for the interview still running on this job and picks it up. Without that, answers stop being
  // recorded and starting again opens a second interview. Picking one up does not send the
  // opening message again: the interviewer already said it.
  const sessionRef = useRef<MockSession | null>(null);
  sessionRef.current = session;
  useEffect(() => {
    if (!profileId || !jobId) return;
    // A page that moved to another job is no longer showing that job's interview.
    if (sessionRef.current && sessionRef.current.job_id !== jobId) {
      setSession(null);
      onSessionChange?.(null);
    }
    let cancelled = false;
    void getActiveMockSession(profileId, jobId)
      .then((found) => {
        if (cancelled || !found || sessionRef.current?.status === "active") return;
        setSession(found);
        // The cards show the level this interview was started with, not what the profile suggests.
        if (found.level) setLevel(found.level);
        onSessionChange?.(found.id);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // onSessionChange is a state setter from the page; it does not change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId, jobId]);

  const job = jobs.find((j) => j.id === jobId) ?? null;

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
    if (!profileId || !level) return;
    setBusy(true);
    setError(null);
    try {
      // A round is always against a job: the JD is what the questions and the review are judged by.
      const next = await createMockSession({
        profile_id: profileId,
        mode: "target",
        job_id: jobId,
        kind,
        style,
        level,
      });
      setSession(next);
      onSessionChange?.(next.id);
      onStarted?.(next);
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
      const finished = await completeMockSession(session.id);
      setSession(finished);
      setFinishedId(finished.id);
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
        <div className="space-y-2">
          <span className="label-meta">岗位（必填）</span>
          {jobs.length > 0 ? (
            <Select
              className="w-full"
              value={jobId ?? ""}
              disabled={active}
              onChange={(e) => onJobChange?.(e.target.value || null)}
            >
              <option value="">请选择岗位</option>
              {jobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {j.company} · {j.title}
                </option>
              ))}
            </Select>
          ) : (
            <p className="text-sm text-ink-600">
              还没有保存的岗位。
              <Link href="/jobs" className="ml-1 font-medium text-brand-700 underline underline-offset-2">
                去粘贴 JD
              </Link>
              ，保存后回到这里选择。
            </p>
          )}
          <p className="text-xs text-ink-500">
            问题和评审都按这份 JD 的要求，结合当前激活的简历档案。
          </p>
        </div>

        <div className="mt-3">
          <span className="label-meta">面试级别</span>
          {recommendation ? (
            <>
              <div className="mt-1.5 grid grid-cols-1 gap-2 sm:grid-cols-2" role="radiogroup" aria-label="面试级别">
                {recommendation.levels.map((option) => {
                  const chosen = level === option.key;
                  return (
                    <button
                      key={option.key}
                      type="button"
                      role="radio"
                      aria-checked={chosen}
                      disabled={active}
                      onClick={() => setLevel(option.key)}
                      className={`rounded-lg border p-3 text-left transition disabled:opacity-60 ${
                        chosen
                          ? "border-brand-500 bg-brand-50"
                          : "border-surface-border bg-surface hover:border-brand-200"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <span className="text-sm font-semibold text-ink-900">{option.label}</span>
                        <span className="text-xs text-ink-500">
                          对照 {option.benchmark} · {option.years}
                        </span>
                        {recommendation.recommended === option.key ? (
                          <span className="badge badge-brand ml-auto">推荐</span>
                        ) : null}
                      </span>
                      <span className="mt-1 block text-xs leading-relaxed text-ink-600">
                        {option.requirement}
                      </span>
                    </button>
                  );
                })}
              </div>
              <p className="mt-1.5 text-xs text-ink-500">
                {recommendation.reason ?? "档案里的经历没有可读的起止时间，请自己选一个级别。"}
                级别决定问题问到多深，不改变评分标准。对照 P 序列只是参考，不是阿里的官方标准。
              </p>
            </>
          ) : recommendationFailed ? (
            <p className="mt-1.5 text-sm text-ink-600">没能读取面试级别，请刷新页面后重试。</p>
          ) : (
            <p className="mt-1.5 text-sm text-ink-500">正在根据档案推荐级别…</p>
          )}
        </div>

        <div className="mt-3">
          <span className="label-meta">题数</span>
          <div className="segment mt-1.5">
            {KIND_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                disabled={active}
                onClick={() => setKind(option.id)}
                className={`segment-item ${kind === option.id ? "segment-item-active" : ""}`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-ink-500">
            {KIND_OPTIONS.find((o) => o.id === kind)?.hint}
          </p>
        </div>

        <div className="mt-3">
          <span className="label-meta">面试官风格</span>
          <div className="segment mt-1.5 flex-wrap">
            {STYLE_OPTIONS.map((option) => (
              <button
                key={option.id}
                type="button"
                disabled={active}
                onClick={() => setStyle(option.id)}
                className={`segment-item ${style === option.id ? "segment-item-active" : ""}`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-ink-500">
            {STYLE_OPTIONS.find((o) => o.id === style)?.hint} 风格只改变提问方式，题目覆盖和评审标准相同。
          </p>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={busy || active || !jobId || !level}
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

        {!active && !jobId ? (
          <p className="mt-2 text-xs text-ink-500">先选择岗位（或粘贴 JD）才能开始。</p>
        ) : null}
        {!active && jobId && !level && recommendation ? (
          <p className="mt-2 text-xs text-ink-500">请先选择面试级别。</p>
        ) : null}

        {session && active ? <MockProgress session={session} active={active} /> : null}

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
                <Select
                  className="mt-1.5 w-full"
                  value={qType}
                  onChange={(e) => setQType(e.target.value)}
                >
                  {TYPES.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.label}
                    </option>
                  ))}
                </Select>
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

      {finishedId ? (
        <p className="notice notice-info">
          模拟面试已结束。独立评审会根据你的回答写报告，打开时生成，可能需要一两分钟：
          <Link href={`/mock-reports/${finishedId}`} className="ml-1 font-medium underline">
            查看报告
          </Link>
        </p>
      ) : null}
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
