"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState } from "@/components/ui/EmptyState";
import { IconArrowRight, IconCheck, IconDoc, IconInfo, IconSpark } from "@/components/ui/Icon";
import {
  listInterviews,
  listMockSessions,
  type MockSessionListItem,
  logQuestion,
  saveInterview,
  type InterviewSummary,
} from "@/lib/api/coach";
import { userFacingApiError } from "@/lib/api/user-error";
import { useAuth } from "@/lib/auth/AuthProvider";
import { formatDateTime } from "@/lib/datetime";

const STYLE_LABEL: Record<string, string> = {
  gentle: "温和引导",
  standard: "标准",
  pressure: "压力",
  deep: "业务深挖",
};

const ENDED_LABEL: Record<string, string> = {
  completed: "正常结束",
  user_ended: "提前结束",
  timeout: "未完成结束",
  superseded: "被新一轮取代",
};

export default function InterviewsPage() {
  const { context } = useAuth();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [date, setDate] = useState("");
  const [stems, setStems] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [ok, setOk] = useState(false);
  // Keep completed question writes on retry; an archive failure must not duplicate them.
  const [savedQuestions, setSavedQuestions] = useState<Record<string, string>>({});
  const profileId = context?.active_profile_id;
  const [history, setHistory] = useState<InterviewSummary[]>([]);
  const [historyError, setHistoryError] = useState("");
  const [mockHistory, setMockHistory] = useState<MockSessionListItem[]>([]);
  const [mockError, setMockError] = useState("");

  useEffect(() => {
    setHistory([]);
    setHistoryError("");
    setMockHistory([]);
    setMockError("");
    if (!profileId) return;
    let active = true;
    listInterviews(profileId)
      .then((r) => {
        if (active) setHistory(r.interviews);
      })
      .catch((e) => {
        if (active) setHistoryError(userFacingApiError(e, "读取失败"));
      });
    listMockSessions(profileId)
      .then((r) => {
        if (active) setMockHistory(r.mock_sessions);
      })
      .catch((e) => {
        // Said, not hidden: an error here would otherwise read as "no finished interviews".
        if (active) setMockError(userFacingApiError(e, "读取模拟面试失败"));
      });
    return () => {
      active = false;
    };
  }, [profileId]);

  async function save() {
    if (!profileId || busy) return;
    setBusy(true);
    setMessage("");
    setOk(false);
    const done = { ...savedQuestions };
    try {
      const lines = [...new Set(stems.split("\n").map((x) => x.trim()).filter(Boolean))];
      if (lines.some((x) => x.length < 4 || x.length > 4000)) {
        throw new Error("每个题干需为 4–4000 字");
      }
      const ids: string[] = [];
      for (const stem of lines) {
        const key = JSON.stringify([profileId, company, role, stem]);
        if (!done[key]) {
          const q = await logQuestion(profileId, {
            stem,
            source: "real",
            company,
            role_title: role,
          });
          done[key] = q.id;
          setSavedQuestions({ ...done });
        }
        ids.push(done[key]);
      }
      await saveInterview(profileId, {
        company,
        role_title: role,
        interview_date: date,
        notes,
        question_ids: ids,
      });
      setOk(true);
      setMessage("面试已归档，题目已进入个人题库。");
      setStems("");
      setNotes("");
      setSavedQuestions({});
      // Archive is already committed; a refresh failure must not invite a duplicate save.
      try {
        setHistory((await listInterviews(profileId)).interviews);
        setHistoryError("");
      } catch {
        setHistoryError("面试已保存，但历史刷新失败。请刷新页面查看，不必再次归档。");
      }
    } catch (e) {
      setOk(false);
      setMessage(userFacingApiError(e, "保存失败，请重试"));
    } finally {
      setBusy(false);
    }
  }

  if (context?.actor !== "user") {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-section">
        <PageHeader eyebrow="复盘" title="真实面试归档" />
        <EmptyState
          icon={<IconSpark />}
          title="登录后归档真实面试"
          description="面试记录属于你的个人数据，需要登录才能保存。"
          action={
            <Link href="/auth/login" className="btn btn-md btn-primary">
              去登录
              <IconArrowRight className="h-4 w-4" />
            </Link>
          }
        />
      </div>
    );
  }

  if (!profileId) {
    return (
      <div className="mx-auto w-full max-w-3xl space-y-section">
        <PageHeader eyebrow="复盘" title="真实面试归档" />
        <EmptyState
          icon={<IconSpark />}
          title="先建好你的档案"
          action={
            <Link href="/resume-agent" className="btn btn-md btn-primary">
              去上传简历
            </Link>
          }
        />
      </div>
    );
  }

  const ready = Boolean(company.trim() && role.trim() && date);
  const stemCount = stems.split("\n").map((x) => x.trim()).filter(Boolean).length;

  return (
    <div className="mx-auto w-full max-w-3xl space-y-section">
      <PageHeader
        eyebrow="复盘"
        title="真实面试归档"
        description="面试结束趁热记下来。被问到的题会进入你的个人题库，下一轮模拟会抽回来再练一遍。"
      />

      <p className="notice notice-info">
        <IconInfo className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          当前版本不监听会议、不提供实时作答提示。请不要上传未获授权的他人个人信息或公司机密。
        </span>
      </p>

      <section className="card card-pad space-y-4">
        <div className="grid gap-4 sm:grid-cols-3">
          <label className="block">
            <span className="label-meta">公司</span>
            <input
              className="field mt-1.5"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              placeholder="例如：某电商平台"
            />
          </label>
          <label className="block">
            <span className="label-meta">岗位</span>
            <input
              className="field mt-1.5"
              value={role}
              onChange={(e) => setRole(e.target.value)}
              placeholder="例如：后端工程师"
            />
          </label>
          <label className="block">
            <span className="label-meta">面试日期</span>
            <input
              type="date"
              className="field mt-1.5"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </label>
        </div>

        <label className="block">
          <span className="label-meta">被问到的问题</span>
          <span className="ml-2 text-micro text-ink-500">一行一道，可留空</span>
          <textarea
            rows={5}
            className="field mt-1.5 resize-y"
            value={stems}
            onChange={(e) => setStems(e.target.value)}
            placeholder={"介绍一下你最有挑战的项目\n如果流量翻十倍你会怎么改"}
          />
          {stemCount > 0 ? (
            <span className="mt-1.5 inline-block text-micro text-ink-500">
              将记入 {stemCount} 道题
            </span>
          ) : null}
        </label>

        <label className="block">
          <span className="label-meta">复盘笔记</span>
          <textarea
            rows={4}
            className="field mt-1.5 resize-y"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="哪里答得顺、哪里被追问住了、下次要换的说法"
          />
        </label>

        <div className="flex flex-wrap items-center gap-3 border-t border-surface-border pt-4">
          <button
            type="button"
            disabled={busy || !ready}
            onClick={() => void save()}
            className="btn btn-md btn-primary"
          >
            {busy ? (
              <>
                <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/35 border-t-white" />
                保存中…
              </>
            ) : (
              "归档并保存题目"
            )}
          </button>
          {!ready && !busy ? (
            <span className="text-xs text-ink-500">公司、岗位、日期为必填</span>
          ) : null}
          <Link href="/coach-agent?intent=archive" className="btn btn-md btn-secondary ml-auto">
            让面试教练帮我记
          </Link>
        </div>

        {message ? (
          <p className={`notice ${ok ? "notice-success" : "notice-danger"}`} role="status">
            {ok ? <IconCheck className="mt-0.5 h-4 w-4 shrink-0" /> : null}
            <span>
              {message}
              {ok ? (
                <>
                  {" "}
                  <Link href="/bank" className="font-medium underline">
                    去题库再练
                  </Link>
                </>
              ) : null}
            </span>
          </p>
        ) : null}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold text-ink-800">模拟面试报告</h2>
          {mockHistory.length ? (
            <span className="text-xs text-ink-500">共 {mockHistory.length} 场</span>
          ) : null}
        </div>
        {mockError ? (
          <p className="text-sm text-danger-700">{mockError}</p>
        ) : mockHistory.length === 0 ? (
          <EmptyState compact icon={<IconDoc />} title="还没有完成的模拟面试" />
        ) : (
          <ul className="space-y-2">
            {mockHistory.map((m) => (
              <li key={m.id} className="card card-pad flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="badge badge-neutral tabular-nums">
                    {formatDateTime(m.started_at)}
                  </span>
                  <span className="text-sm text-ink-800">
                    {STYLE_LABEL[m.style ?? ""] ?? "标准"} · {m.question_count} 题 ·{" "}
                    {ENDED_LABEL[m.ended_reason ?? ""] ?? "已结束"}
                  </span>
                </div>
                {m.has_report ? (
                  <Link href={`/mock-reports/${m.id}`} className="btn btn-sm btn-secondary">
                    查看报告
                  </Link>
                ) : (
                  <span className="text-xs text-ink-500">报告打开时生成</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-sm font-semibold text-ink-800">已归档面试</h2>
          {history.length ? (
            <span className="text-xs text-ink-500">最近 {history.length} 条</span>
          ) : null}
        </div>

        {historyError ? (
          <p className="notice notice-warn" role="alert">
            {historyError}
          </p>
        ) : null}

        {history.length === 0 && !historyError ? (
          <EmptyState compact icon={<IconDoc />} title="还没有归档记录" />
        ) : (
          <ul className="space-y-2">
            {history.map((r) => (
              <li key={r.id} className="card card-pad">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="badge badge-neutral tabular-nums">{r.interview_date}</span>
                  <h3 className="text-sm font-medium text-ink-900">
                    {r.company} · {r.role_title}
                  </h3>
                </div>
                {r.notes ? (
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-ink-700">
                    {r.notes}
                  </p>
                ) : null}
                {r.question_ids.length ? (
                  <div className="mt-2.5 flex flex-wrap gap-1.5 border-t border-surface-border pt-2.5">
                    {r.question_ids.map((id, i) => (
                      <Link
                        key={id}
                        href={`/bank/${encodeURIComponent(id)}`}
                        className="badge badge-brand hover:bg-brand-100"
                      >
                        题目 {i + 1}
                      </Link>
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
