"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getMockReport,
  type MockReport,
  type MockReportQuestion,
} from "@/lib/api/coach";
import { useAuth } from "@/lib/auth/AuthProvider";
import { userFacingApiError } from "@/lib/api/user-error";
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
          {item.answer || "（未作答，已跳过）"}
        </p>
      </div>

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
      <div className="card mx-auto max-w-2xl p-6">
        <p className="text-sm text-ink-700">{report.message ?? "报告暂不可用。"}</p>
        <Link className="btn btn-secondary btn-sm mt-4 inline-flex" href="/coach-agent">
          返回面试辅导
        </Link>
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
