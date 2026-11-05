"use client";

import { Suspense, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { CoachFlywheel } from "@/components/coach/CoachFlywheel";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { useAuth } from "@/lib/auth/AuthProvider";

function CoachAgentInner() {
  const { context, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");
  const [mockSessionId, setMockSessionId] = useState<string | null>(null);
  const [autoStart, setAutoStart] = useState<{ id: string; message: string } | null>(null);
  const practiceQid = searchParams.get("practice");
  // Arrived from the archive page: the coach records a real interview instead of running a mock.
  const intent = searchParams.get("intent") === "archive" ? "archive" : null;

  // The job lives in the URL, so a link to this page with a job already set still opens on it.
  function changeJob(id: string | null) {
    const params = new URLSearchParams(searchParams.toString());
    if (id) params.set("job_id", id);
    else params.delete("job_id");
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }

  const subtitle = jobId
    ? "对着当前岗位模拟、记题、抽库再练"
    : "无 JD 也可练手；选择岗位后可进行目标岗模拟";

  return (
    <div className="flex min-h-0 flex-1 flex-col space-y-3">
      <EmailVerificationBanner />
      {loading ? <p className="text-sm text-ink-500">加载中…</p> : null}
      <AgentWorkbench
        pageKey={`coach-agent-${jobId ?? "general"}`}
        title="面试教练"
        subtitle={subtitle}
        profileId={profileId}
        jobId={jobId}
        uiContext={{
          page: "coach-agent",
          step: "mock",
          focus: null,
          mock_session_id: mockSessionId,
          intent,
        }}
        roleId="coach-mock"
        autoStart={autoStart}
        disabled={context?.actor !== "user"}
        placeholder="回答面试官问题，或说「下一题」…"
      >
        <CoachFlywheel
          profileId={profileId}
          jobId={jobId}
          practiceQid={practiceQid}
          onSessionChange={setMockSessionId}
          onJobChange={changeJob}
          onStarted={(started) =>
            setAutoStart({ id: started.id, message: "你好，我准备好了，可以开始面试了。" })
          }
          disabled={context?.actor !== "user"}
        />
      </AgentWorkbench>
    </div>
  );
}

export default function CoachAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-500">加载中…</p>}>
      <CoachAgentInner />
    </Suspense>
  );
}
