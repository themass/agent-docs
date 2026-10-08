"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import {
  createMockSession,
  getMockSession,
  getQuestionDetail,
  logQuestion,
  type MockSession,
} from "@/lib/api/coach";
import { listJobs, type Job } from "@/lib/api/jobs";

const TYPES = [
  { id: "behavioral", label: "行为/STAR" },
  { id: "project_deep", label: "项目深挖" },
  { id: "technical", label: "技术" },
  { id: "system_design", label: "系统设计" },
  { id: "other", label: "其他" },
];

type Props = {
  profileId: string | null;
  jobId: string | null;
  practiceQid: string | null;
  disabled: boolean;
};

export function CoachFlywheel({ profileId, jobId, practiceQid, disabled }: Props) {
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
  const goalHint = useMemo(() => {
    if (logged >= 3) return "本轮已满 3 题，可以再开一轮抽库。";
    return `本轮已记 ${logged} / 3 题`;
  }, [logged]);

  async function onStart() {
    if (!profileId) return;
    setBusy(true);
    setError(null);
    try {
      const next = await createMockSession({
        profile_id: profileId,
        mode,
        job_id: jobId,
      });
      setSession(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
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
      const refreshed = await getMockSession(session.id);
      setSession(refreshed);
      setStem("");
      setAnswer("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "记题失败");
    } finally {
      setBusy(false);
    }
  }

  if (disabled) {
    return <p className="text-sm text-amber-700">请登录后开始模拟面试。</p>;
  }
  if (!profileId) {
    return (
      <p className="text-sm text-slate-600">
        请先{" "}
        <Link href="/resume-agent" className="underline">
          上传简历
        </Link>
        。
      </p>
    );
  }

  return (
    <div className="space-y-5 text-sm">
      <section className="rounded-2xl border border-surface-border bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-slate-900">1. 开模拟</h2>
        {!jobId ? (
          <p className="mt-2 text-slate-600">
            请从{" "}
            <Link href="/applications" className="text-brand-700 underline">
              投递看板
            </Link>{" "}
            或{" "}
            <Link href="/jobs" className="text-brand-700 underline">
              定向岗位
            </Link>{" "}
            带岗进入，才能抽库和对着 JD 练。
          </p>
        ) : (
          <>
            <p className="mt-2 text-slate-700">
              {job ? `${job.company} · ${job.title}` : `岗位 ${jobId}`}
            </p>
            <label className="mt-3 block text-xs text-slate-500">
              语气
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
                value={mode}
                onChange={(e) => setMode(e.target.value as "warmup" | "target")}
              >
                <option value="warmup">练手（支持、给空间）</option>
                <option value="target">目标岗（追问更紧）</option>
              </select>
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onStart()}
              className="mt-3 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {busy ? "创建中…" : session ? "再开一轮" : "开始本轮模拟"}
            </button>
          </>
        )}
      </section>

      <section className="rounded-2xl border border-surface-border bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-slate-900">2. 本轮题单</h2>
        <p className="mt-1 text-xs text-slate-500">
          Agent 可以出题；你也可以在下面补记，不依赖模型自觉写库。{goalHint}
        </p>
        {!session ? (
          <p className="mt-2 text-slate-500">先开始本轮模拟。</p>
        ) : (
          <>
            <ul className="mt-3 space-y-2">
              {session.questions.map((q) => (
                <li key={q.id} className="rounded-xl border border-slate-200 px-3 py-2">
                  <p className="text-slate-800">{q.stem}</p>
                  <p className="mt-1 flex flex-wrap gap-2 text-[11px] text-slate-500">
                    {q.from_bank ? (
                      <span className="rounded bg-brand-50 px-1.5 py-0.5 text-brand-700">
                        本题来自你的题库
                      </span>
                    ) : (
                      <span>本轮新记</span>
                    )}
                    <Link href={`/bank/${q.id}`} className="underline">
                      对比答法
                    </Link>
                  </p>
                </li>
              ))}
              {session.questions.length === 0 ? (
                <li className="text-slate-500">还没有题。右侧开聊或在下面补记。</li>
              ) : null}
            </ul>
            <label className="mt-4 block text-xs font-medium text-slate-700">
              补记题干
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                rows={3}
                value={stem}
                onChange={(e) => setStem(e.target.value)}
                placeholder="把面试官的问题写在这里"
              />
            </label>
            <label className="mt-2 block text-xs text-slate-500">
              题型
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 px-2 py-1.5 text-sm"
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
            <label className="mt-2 block text-xs text-slate-500">
              我的回答（可选，会记一版练习）
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                rows={3}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={busy || stem.trim().length < 4}
              onClick={() => void onLog()}
              className="mt-3 rounded-lg border border-slate-200 px-4 py-2 text-sm disabled:opacity-50"
            >
              记入题库
            </button>
          </>
        )}
      </section>

      <section className="rounded-2xl border border-surface-border bg-white p-4 shadow-card">
        <h2 className="text-sm font-semibold text-slate-900">3. 题库</h2>
        <p className="mt-2">
          <Link
            href={jobId ? `/bank?job_id=${encodeURIComponent(jobId)}` : "/bank"}
            className="text-brand-700 underline"
          >
            查看{jobId ? "本岗" : "个人"}题库
          </Link>
        </p>
        <p className="mt-2 text-xs text-slate-500">
          记满 3 题后再开一轮，系统会抽一道已入库的题，并在题单上标记「来自题库」。
        </p>
      </section>

      {error ? <p className="text-sm text-red-600">{error}</p> : null}
    </div>
  );
}
