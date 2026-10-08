"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { CoachFlywheel } from "@/components/coach/CoachFlywheel";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { useAuth } from "@/lib/auth/AuthProvider";

function CoachAgentInner() {
  const { context, loading } = useAuth();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");
  const practiceQid = searchParams.get("practice");

  const subtitle = jobId
    ? "对着当前岗位模拟、记题、抽库再练"
    : "从投递看板带岗进入，才能抽库和对着 JD 练";

  return (
    <div className="flex min-h-0 flex-1 flex-col space-y-3">
      <EmailVerificationBanner />
      {loading ? <p className="text-sm text-neutral-500">加载中…</p> : null}
      <AgentWorkbench
        pageKey={`coach-agent-${jobId ?? "general"}`}
        title="面试辅导"
        subtitle={subtitle}
        profileId={profileId}
        jobId={jobId}
        skillHint="coach-mock"
        kind="coach"
        disabled={context?.actor !== "user"}
        placeholder="回答面试官问题，或说「下一题」…"
      >
        <CoachFlywheel
          profileId={profileId}
          jobId={jobId}
          practiceQid={practiceQid}
          disabled={context?.actor !== "user"}
        />
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
