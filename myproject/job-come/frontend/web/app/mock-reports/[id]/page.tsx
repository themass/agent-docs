"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getMockReport,
  retryMockReport,
  type MockReport,
  type MockReportQuestion,
  type MockReportSummaryItem,
} from "@/lib/api/coach";
import { useAuth } from "@/lib/auth/AuthProvider";
import { ApiError } from "@/lib/api/errors";
import { userFacingApiError } from "@/lib/api/user-error";
import { nextPoll, START, type PollStop } from "@/lib/report-poll";
import { formatDateTime } from "@/lib/datetime";

const DIMENSION_LABEL: Record<string, string> = {
  structure: "结构",
  relevance: "相关性",
  depth: "深度",
  communication: "表达",
  reflection: "反思",
};

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
};

const SEVERITY_LABEL: Record<string, { text: string; tone: string }> = {
  must: { text: "必须修正", tone: "badge-warn" },
  suggest: { text: "建议", tone: "badge-neutral" },
  nit: { text: "细节", tone: "badge-neutral" },
};

function ScoreRow({ scores }: { scores: MockReportQuestion["scores"] }) {
  return (
    <dl className="grid grid-cols-5 gap-2 text-center text-xs">
      {Object.entries(DIMENSION_LABEL).map(([key, label]) => {
        const value = scores[key];
        return (
          <div key={key} className="rounded-md bg-ink-50 px-2 py-2">
            <dt className="text-ink-500">{label}</dt>
            <dd className="mt-1 text-sm font-semibold text-ink-900">
              {value == null ? "无法判断" : value}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

const TIER_TONE: Record<string, string> = {
  need_more: "badge-warn",
  targeted: "badge-warn",
  ready: "badge-brand",
  solid: "badge-success",
};

function SummaryList({ title, items }: { title: string; items: MockReportSummaryItem[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h3 className="text-xs font-medium text-ink-500">{title}</h3>
      <ol className="mt-1.5 flex flex-col gap-2">
        {items.map((item, i) => (
          <li key={i} className="text-sm text-ink-800">
            <span className="font-medium">{i + 1}. </span>
            {item.text}
            {item.quote ? (
              <span className="mt-0.5 block text-xs text-ink-500">你说过：「{item.quote}」</span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** What the report says before any detail: how it went, how ready the candidate looks, what went
 * well and what to fix first. The tier is the server's; it is a reading of this interview, not a
 * prediction of a real one. */
function Conclusion({ report }: { report: MockReport }) {
  const { readiness, summary } = report;
  if (!readiness && !summary) return null;
  return (
    <section className="card flex flex-col gap-4 p-5">
      {readiness ? (
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`badge ${TIER_TONE[readiness.tier] ?? "badge-neutral"}`}>
              {readiness.label}
            </span>
            <h2 className="text-base font-semibold text-ink-900">{readiness.statement}</h2>
          </div>
          <ul className="flex flex-col gap-0.5 text-xs text-ink-500">
            {readiness.basis.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {summary?.verdict ? <p className="text-sm leading-relaxed text-ink-800">{summary.verdict}</p> : null}
      {summary ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <SummaryList title="做得好的" items={summary.strengths} />
          <SummaryList title="最该先改的" items={summary.priorities} />
        </div>
      ) : null}
      <p className="text-xs text-ink-500">
        这是对这一场模拟面试的读法，不是对真实面试结果的预测。
      </p>
    </section>
  );
}

function QuestionBlock({ item, index }: { item: MockReportQuestion; index: number }) {
  return (
    <section className="card flex flex-col gap-3 p-5">
      <header>
        <p className="text-xs text-ink-500">第 {index + 1} 题</p>
        <h2 className="mt-1 text-sm font-semibold text-ink-900">{item.stem || "（题目已不可用）"}</h2>
      </header>

      <div>
        <p className="text-xs font-medium text-ink-500">你的回答</p>
        <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
          {item.answer || (item.skipped ? "（已跳过）" : "（未作答）")}
        </p>
      </div>

      {item.follow_ups.length > 0 && (
        <div className="flex flex-col gap-3 border-l-2 border-surface-border pl-3">
          {item.follow_ups.map((follow) => (
            <div key={follow.question_id}>
              <p className="text-xs text-ink-500">追问</p>
              <p className="text-sm font-medium text-ink-900">{follow.stem}</p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
                {follow.answer || "（未作答）"}
              </p>
            </div>
          ))}
        </div>
      )}

      <ScoreRow scores={item.scores} />

      {Object.entries(item.evidence).length > 0 && (
        <ul className="flex flex-col gap-1 text-xs text-ink-600">
          {Object.entries(item.evidence).map(([key, quote]) => (
            <li key={key}>
              <span className="font-medium">{DIMENSION_LABEL[key] ?? key}依据：</span>
              「{quote}」
            </li>
          ))}
        </ul>
      )}

      {item.praise && (
        <p className="text-sm text-ink-800">
          <span className="font-medium">做得好：</span>
          {item.praise}
        </p>
      )}

      {item.fixes.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs font-medium text-ink-500">修正</p>
          {item.fixes.map((fix, i) => (
            <div key={i} className="flex gap-2 text-sm text-ink-800">
              <span className={`badge ${SEVERITY_LABEL[fix.severity].tone} shrink-0`}>
                {SEVERITY_LABEL[fix.severity].text}
              </span>
              <span className="whitespace-pre-wrap">{fix.text}</span>
            </div>
          ))}
        </div>
      )}

      {item.reference.length > 0 && (
        <div className="flex flex-col gap-2 rounded-md bg-ink-50 p-3">
          <p className="text-xs font-medium text-ink-500">
            合理答案（基于你的档案，仅供参考，不是标准答案）
          </p>
          {item.reference.map((fact, i) => (
            <p key={i} className="text-sm text-ink-800">
              {fact.text}
              <span className="ml-2 text-xs text-ink-500">
                {fact.status === "sourced" ? `出处：${fact.source}` : "待补充：档案中没有依据"}
              </span>
            </p>
          ))}
        </div>
      )}
    </section>
  );
}

export default function MockReportPage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id;
  const { context, loading: authLoading } = useAuth();
  const signedIn = context?.actor === "user";
  const [report, setReport] = useState<MockReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pollStopped, setPollStopped] = useState<PollStop | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  useEffect(() => {
    if (!signedIn) return;
    let cancelled = false;
    getMockReport(sessionId)
      .then((data) => {
        if (!cancelled) setReport(data);
      })
      .catch((err) => {
        if (!cancelled) setError(userFacingApiError(err, "加载报告失败，请稍后重试。"));
      });
    return () => {
      cancelled = true;
    };
  }, [signedIn, sessionId]);

  // A report still being generated is asked for again, one request after the last answer (never two
  // at once), more slowly while the server is struggling, and not at all once a request is refused
  // for good or the wait has gone on far too long. The page says so when it stops.
  const pending = report?.status === "pending";
  useEffect(() => {
    if (!pending) return;
    let cancelled = false;
    let timer: number | undefined;
    let state = START;
    setPollStopped(null);

    const poll = () => {
      getMockReport(sessionId)
        .then((data) => {
          if (cancelled) return;
          setReport(data);
          schedule({ ok: true });
        })
        .catch((err: unknown) => {
          if (cancelled) return;
          schedule({ ok: false, status: err instanceof ApiError ? err.status : null });
        });
    };
    const schedule = (outcome: Parameters<typeof nextPoll>[1]) => {
      const step = nextPoll(state, outcome);
      state = step.state;
      if (step.stopped) {
        setPollStopped(step.stopped);
        return;
      }
      timer = window.setTimeout(poll, step.delayMs ?? 0);
    };

    timer = window.setTimeout(poll, nextPoll(START, { ok: true }).delayMs ?? 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [pending, sessionId]);

  async function onRetry() {
    setRetrying(true);
    setRetryError(null);
    try {
      setReport(await retryMockReport(sessionId));
    } catch (err) {
      setRetryError(userFacingApiError(err, "重新生成失败，请稍后重试。"));
    } finally {
      setRetrying(false);
    }
  }

  if (authLoading) return <p className="text-sm text-ink-500">正在加载…</p>;
  if (!signedIn) {
    return (
      <div className="card bg-sheen mx-auto max-w-md px-6 py-10 text-center">
        <p className="text-sm text-ink-600">
          请先{" "}
          <Link className="font-medium text-brand-700 hover:text-brand-800" href="/auth/login">
            登录
          </Link>{" "}
          再查看模拟面试报告。
        </p>
      </div>
    );
  }
  if (error) return <p className="text-sm text-ink-600">{error}</p>;
  if (!report) return <p className="text-sm text-ink-500">正在加载报告…</p>;
  if (report.status !== "ready") {
    return (
      <div className="card mx-auto max-w-2xl p-6" aria-live="polite">
        <p className="text-sm font-medium text-ink-900">
          {report.status === "pending"
            ? "评审进行中"
            : report.status === "failed"
              ? "报告没有生成出来"
              : "报告暂不可用"}
        </p>
        <p className="mt-1 text-sm text-ink-700">{report.message ?? "报告暂不可用。"}</p>
        {report.status === "pending" && !pollStopped ? (
          <p className="mt-1 text-xs text-ink-500">页面会自动刷新，你也可以先离开，稍后回来看。</p>
        ) : null}
        {report.status === "pending" && pollStopped ? (
          <p className="mt-1 text-xs text-ink-500">
            {pollStopped === "rejected"
              ? "没法再读取这份报告了，可能是登录已过期。请刷新页面或重新登录。"
              : "等了很久还没有结果，页面不再自动刷新。请稍后手动刷新页面。"}
          </p>
        ) : null}
        {report.status === "failed" && !report.can_retry ? (
          <p className="mt-1 text-xs text-ink-500">已经重试过多次，这份报告不能再重新生成了。</p>
        ) : null}
        {retryError ? (
          <p className="notice notice-danger mt-3 text-xs" role="alert">
            {retryError}
          </p>
        ) : null}
        <div className="mt-4 flex flex-wrap gap-2">
          {report.status === "failed" && report.can_retry ? (
            <button
              type="button"
              disabled={retrying}
              onClick={() => void onRetry()}
              className="btn btn-primary btn-sm"
            >
              {retrying ? "正在提交…" : "重新生成"}
            </button>
          ) : null}
          <Link className="btn btn-secondary btn-sm inline-flex" href="/coach-agent">
            返回面试辅导
          </Link>
        </div>
      </div>
    );
  }

  const averages = Object.entries(DIMENSION_LABEL).map(([key, label]) => ({
    key,
    label,
    value: report.overall[key],
  }));

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
      <header className="flex flex-col gap-2">
        <h1 className="text-lg font-semibold text-ink-900">模拟面试报告</h1>
        <p className="text-xs text-ink-500">
          本报告由独立评审根据你的原始回答评出，面试官没有参与打分，也看不到评审的结论。
        </p>
        <p className="text-xs text-ink-500">
          面试官风格：{STYLE_LABEL[report.style ?? ""] ?? "标准"} · 结束方式：
          {ENDED_LABEL[report.ended_reason ?? ""] ?? "—"} · 开始于{" "}
          {formatDateTime(report.started_at)}
        </p>
      </header>

      <Conclusion report={report} />

      <section className="card p-5">
        <h2 className="text-sm font-semibold text-ink-900">五维平均</h2>
        <dl className="mt-3 grid grid-cols-5 gap-2 text-center">
          {averages.map((item) => (
            <div key={item.key} className="rounded-md bg-ink-50 px-2 py-3">
              <dt className="text-xs text-ink-500">{item.label}</dt>
              <dd className="mt-1 text-lg font-semibold text-ink-900">
                {item.value == null ? "—" : item.value}
              </dd>
            </div>
          ))}
        </dl>
        {(report.checks.rejected_evidence ?? 0) > 0 && (
          <p className="mt-3 text-xs text-ink-500">
            有 {report.checks.rejected_evidence} 个评分因找不到你的原话作依据而未计入，显示为“无法判断”。
          </p>
        )}
        {(report.checks.pending_facts ?? 0) > 0 && (
          <p className="mt-1 text-xs text-ink-500">
            有 {report.checks.pending_facts} 条参考事实在档案里找不到出处，已标为待补充。
          </p>
        )}
      </section>

      {report.trend && report.trend.first_five != null && report.trend.last_five != null ? (
        <section className="card p-5">
          <h2 className="text-sm font-semibold text-ink-900">前后对比</h2>
          <p className="mt-2 text-sm text-ink-800">
            前 5 题平均 {report.trend.first_five}，后 5 题平均 {report.trend.last_five}。
            <span className="ml-1 text-ink-500">
              {report.trend.last_five - report.trend.first_five >= 1
                ? "越答越好。"
                : report.trend.last_five - report.trend.first_five <= -1
                  ? "后面的回答掉了下来。"
                  : "前后基本持平。"}
            </span>
          </p>
        </section>
      ) : null}

      {report.coverage && report.coverage.total > 0 ? (
        <section className="card p-5">
          <h2 className="text-sm font-semibold text-ink-900">必备项覆盖</h2>
          <p className="mt-2 text-sm text-ink-800">
            岗位必备项 {report.coverage.total} 项：问到 {report.coverage.asked} 项，回答达标{" "}
            {report.coverage.meet} 项。
          </p>
        </section>
      ) : null}

      {report.suggestions.length > 0 ? (
        <section className="card flex flex-col gap-3 p-5">
          <h2 className="text-sm font-semibold text-ink-900">改进建议</h2>
          {report.suggestions.map((item) => (
            <div key={item.dimension} className="flex flex-col gap-1 rounded-md bg-ink-50 p-3">
              <p className="text-sm font-medium text-ink-900">
                {item.label}（均分 {item.average}）
              </p>
              <p className="text-sm text-ink-800">练习：{item.practice}</p>
              {item.question_id ? (
                <Link
                  href={`/bank/${encodeURIComponent(item.question_id)}`}
                  className="text-xs font-medium text-brand-700 hover:text-brand-800"
                >
                  回到这一题练习
                </Link>
              ) : null}
            </div>
          ))}
        </section>
      ) : null}

      {report.brief ? (
        <p className="text-xs text-ink-500">
          这是热身的简版报告。完整模拟（20 题）会给出逐题的回答、证据、修正和合理答案。
        </p>
      ) : (
        report.questions.map((item, index) => (
          <QuestionBlock key={item.question_id} item={item} index={index} />
        ))
      )}
    </div>
  );
}
