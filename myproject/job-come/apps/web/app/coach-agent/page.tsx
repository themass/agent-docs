"use client";

import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { useAuth } from "@/lib/auth/AuthProvider";

function CoachAgentInner() {
  const { context, loading } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");

  const subtitle = jobId
    ? `已绑定岗位 ${jobId} · 模拟面试、真题归档、答题迭代`
    : "模拟面试、真题归档、答题迭代。从定向岗位页可带 job_id 进入。";

  return (
    <div className="space-y-6">
      <EmailVerificationBanner />
      {loading ? <p className="text-sm text-neutral-500">加载中…</p> : null}

      <AgentWorkbench
        pageKey={`coach-agent-${jobId ?? "general"}`}
        title="面试辅导 Agent"
        subtitle={subtitle}
        profileId={profileId}
        jobId={jobId}
        skillHint="coach-mock"
        kind="coach"
        disabled={context?.actor !== "user"}
        placeholder="描述面试场景，或粘贴面试官问题…"
      >
        <div className="space-y-4 text-sm text-neutral-700">
          <p>
            在此进行<strong>对话式模拟面试</strong>。Agent 会根据档案与岗位上下文提问、点评答案。
          </p>
          {!jobId ? (
            <p>
              建议从{" "}
              <Link href="/jobs" className="underline text-sky-700">
                定向岗位
              </Link>{" "}
              选择目标岗位后进入，以获得 JD 与 prep 上下文。
            </p>
          ) : null}
          <ul className="list-disc space-y-1 pl-5 text-neutral-600">
            <li>右侧可查看 Skill 激活、Tool 调用与 Token 用量</li>
            <li>支持图片/文件附件与语音输入（浏览器 ASR）</li>
            <li>会话刷新后可从本地恢复的 session 续聊</li>
          </ul>
        </div>
      </AgentWorkbench>
    </div>
  );
}

export default function CoachAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-neutral-500">加载中…</p>}>
      <CoachAgentInner />
    </Suspense>
  );
}
