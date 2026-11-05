"use client";

import Link from "next/link";
import { Suspense, useCallback, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { CoachFlywheel } from "@/components/coach/CoachFlywheel";
import { MockBar } from "@/components/coach/MockBar";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { useMockProgress } from "@/hooks/useMockProgress";
import { useAuth } from "@/lib/auth/AuthProvider";

function CoachAgentInner() {
  const { context, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const profileId = context?.active_profile_id ?? null;
  const jobId = searchParams.get("job_id");
  const [mockSessionId, setMockSessionId] = useState<string | null>(null);
  // The round that has just ended, however it ended. Its report is on the way.
  const [endedId, setEndedId] = useState<string | null>(null);
  const [autoStart, setAutoStart] = useState<{ id: string; message: string } | null>(null);
  const practiceQid = searchParams.get("practice");
  // Arrived from the archive page: the coach records a real interview instead of running a mock.
  const intent = searchParams.get("intent") === "archive" ? "archive" : null;

  // Whoever ends a round (the candidate, the interviewer's own end tool, the idle timeout), the page
  // leaves it the same way: the round stops being the one answers are recorded to, and the report
  // notice shows. The server is the only one who knows, so this runs when the server says so.
  const handleEnded = useCallback((id: string) => {
    setEndedId(id);
    setMockSessionId((current) => (current === id ? null : current));
  }, []);
  const reader = useMockProgress(mockSessionId, handleEnded);

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
        conversationTop={(agent) =>
          mockSessionId ? (
            <MockBar
              sessionId={mockSessionId}
              conversation={agent}
              progress={reader}
              onEnded={handleEnded}
            />
          ) : null
        }
        conversationBottom={
          endedId ? (
            <div className="notice notice-success text-sm">
              <span>
                面试结束了，报告由独立评审生成，通常需要一两分钟。
                <Link href={`/mock-reports/${endedId}`} className="ml-1 font-medium underline">
                  查看报告
                </Link>
              </span>
            </div>
          ) : null
        }
      >
        <CoachFlywheel
          profileId={profileId}
          jobId={jobId}
          practiceQid={practiceQid}
          onSessionChange={(id) => {
            setMockSessionId(id);
            // A new round replaces the notice about the last one.
            if (id) setEndedId(null);
          }}
          onJobChange={changeJob}
          onStarted={(started) =>
            setAutoStart({ id: started.id, message: "你好，我准备好了，可以开始面试了。" })
          }
          onFinished={handleEnded}
          progress={reader.progress}
          endedId={endedId}
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
