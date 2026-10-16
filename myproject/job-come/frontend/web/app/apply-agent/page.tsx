"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { IconArrowRight, IconCheck } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth/AuthProvider";

const STEPS = [
  "读你的档案，确认事实基础",
  "解析或绑定这个岗位的 JD",
  "算差距，给出按岗改写建议",
  "你确认后才写回档案",
  "导出前过一遍服务端质检",
];

function ApplyAgentInner() {
  const { context, loading } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");

  return (
    <div className="flex min-h-0 flex-1 flex-col space-y-3">
      <EmailVerificationBanner />
      {loading ? <p className="text-sm text-ink-500">加载中…</p> : null}

      <AgentWorkbench
        pageKey={`apply-agent-${jobId ?? "general"}`}
        title="定向申请"
        subtitle={
          jobId ? "对着这个岗位走完整申请流程" : "从定向岗位页进入可自动绑定岗位"
        }
        profileId={profileId}
        jobId={jobId}
        skillHint="apply-pipeline"
        kind="coach"
        disabled={context?.actor !== "user"}
        placeholder="例如：帮我对这个岗位走完整申请流程并导出 PDF"
      >
        <div className="space-y-4">
          <section className="card card-pad">
            <h2 className="text-sm font-semibold text-ink-900">这条流水线会做什么</h2>
            <ol className="mt-3 space-y-2">
              {STEPS.map((step, i) => (
                <li key={step} className="flex gap-2.5 text-sm text-ink-700">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-micro font-semibold tabular-nums text-brand-700 ring-1 ring-inset ring-brand-100">
                    {i + 1}
                  </span>
                  <span className="leading-relaxed">{step}</span>
                </li>
              ))}
            </ol>
          </section>

          {!jobId ? (
            <section className="card-sunken bg-sheen card-pad">
              <p className="text-sm font-medium text-ink-800">还没绑定岗位</p>
              <p className="mt-1 text-sm leading-relaxed text-ink-600">
                先在定向岗位页保存一份 JD，再从那里进来，Agent 才能对着具体要求改稿。
              </p>
              <Link href="/jobs" className="btn btn-sm btn-primary mt-3">
                去添加岗位
                <IconArrowRight className="h-3.5 w-3.5" />
              </Link>
            </section>
          ) : null}

          <section className="card-sunken card-pad">
            <p className="label-meta">边界</p>
            <ul className="mt-2 space-y-1.5">
              {[
                "写档案前一定会弹确认卡片，模型不能自己落库",
                "导出走服务端质检，没过会说明原因",
                "不代投、不外发，所有动作都由你触发",
              ].map((item) => (
                <li key={item} className="flex gap-2 text-sm text-ink-600">
                  <IconCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success-600" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      </AgentWorkbench>
    </div>
  );
}

export default function ApplyAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-500">加载中…</p>}>
      <ApplyAgentInner />
    </Suspense>
  );
}
