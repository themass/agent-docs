"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { useAuth } from "@/lib/auth/AuthProvider";

function ApplyAgentInner() {
  const { context, loading } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");

  return (
    <div className="space-y-6">
      <EmailVerificationBanner />
      {loading ? <p className="text-sm text-neutral-500">加载中…</p> : null}

      <AgentWorkbench
        pageKey={`apply-agent-${jobId ?? "general"}`}
        title="定向申请 Agent"
        subtitle={
          jobId
            ? `岗位 ${jobId} · fit → 改稿 → 导出流水线`
            : "从定向岗位页进入可自动绑定 job_id"
        }
        profileId={profileId}
        jobId={jobId}
        skillHint="apply-pipeline"
        kind="coach"
        disabled={context?.actor !== "user"}
        placeholder="例如：帮我对这个岗位走完整申请流程并导出 PDF"
      >
        <div className="space-y-4 text-sm text-neutral-700">
          <p>
            对话式完成 <strong>一岗定向申请</strong>：读档案 → 解析/绑定 JD → fit 打分 → 改稿建议 →
            确认后 patch → 调用 apply-pipeline 导出。
          </p>
          {!jobId ? (
            <p>
              请先在{" "}
              <Link href="/jobs" className="underline text-sky-700">
                定向岗位
              </Link>{" "}
              保存 JD，再点「Agent 申请」进入。
            </p>
          ) : null}
          <ul className="list-disc space-y-1 pl-5 text-neutral-600">
            <li>写档案前会弹出确认卡片</li>
            <li>导出仍走服务端 reviewer，失败时会说明原因</li>
            <li>也可在岗位页使用一键「定向申请」REST 按钮</li>
          </ul>
        </div>
      </AgentWorkbench>
    </div>
  );
}

export default function ApplyAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-neutral-500">加载中…</p>}>
      <ApplyAgentInner />
    </Suspense>
  );
}
