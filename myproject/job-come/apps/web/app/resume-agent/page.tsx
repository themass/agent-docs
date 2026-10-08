"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { MergeConflictBanner } from "@/components/auth/MergeConflictBanner";
import { ProfileSwitcher } from "@/components/profile/ProfileSwitcher";
import { ProfileUploader } from "@/components/profile/ProfileUploader";
import { SystemStatusBanner } from "@/components/profile/SystemStatusBanner";
import { WorkflowHeader } from "@/components/profile/WorkflowHeader";
import { ResumeStudio } from "@/components/resume/ResumeStudio";
import { ResumeWorkflowActions } from "@/components/resume/ResumeWorkflowActions";
import { getProfile, type Profile } from "@/lib/api/profile";
import type { ResumeTrack } from "@/lib/api/resume";
import { computeWorkflowSteps, type StudioStep } from "@/lib/resume-workflow";
import type { AgentUiContext, AgentUiFocus } from "@/lib/ui-context";
import { useAuth } from "@/lib/auth/AuthProvider";

function ResumeAgentInner() {
  const { context, loading, refresh } = useAuth();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job_id");
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasElevatePreview, setHasElevatePreview] = useState(false);
  const [hasExported, setHasExported] = useState(false);
  const [studioStep, setStudioStep] = useState<StudioStep>("review");
  const [generateTick, setGenerateTick] = useState(0);
  const [elevateBusy, setElevateBusy] = useState(false);
  const [exportCtx, setExportCtx] = useState<{
    draftId: string;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  } | null>(null);
  const [uiFocus, setUiFocus] = useState<AgentUiFocus | null>(null);
  const jobElevateOnceRef = useRef(false);

  const profileId = profile?.id ?? context?.active_profile_id ?? null;
  const isConfirmed = profile?.status === "confirmed";

  useEffect(() => {
    const id = context?.active_profile_id;
    if (!id) {
      setProfile(null);
      setUiFocus(null);
      return;
    }
    void getProfile(id)
      .then(setProfile)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "加载失败"));
  }, [context?.active_profile_id]);

  useEffect(() => {
    if (!isConfirmed && studioStep !== "review") {
      setStudioStep("review");
    }
  }, [isConfirmed, studioStep]);

  useEffect(() => {
    if (jobId && isConfirmed && !jobElevateOnceRef.current) {
      jobElevateOnceRef.current = true;
      setStudioStep("elevate");
    }
  }, [jobId, isConfirmed]);

  const reloadProfile = useCallback(() => {
    if (!profileId) return;
    void getProfile(profileId).then(setProfile).catch(() => undefined);
  }, [profileId]);

  const canExport = context?.capabilities.includes("export") ?? false;
  const isUser = context?.actor === "user";
  const hasProfile = Boolean(profile);

  const steps = useMemo(
    () =>
      computeWorkflowSteps(profile, {
        hasElevatePreview,
        hasExported,
        currentStep: isConfirmed ? studioStep : "review",
      }),
    [profile, hasElevatePreview, hasExported, isConfirmed, studioStep],
  );

  const handleStepClick = useCallback(
    (stepId: string) => {
      if (stepId === "review") setStudioStep("review");
      if (stepId === "elevate" && isConfirmed) setStudioStep("elevate");
      if (stepId === "export" && isConfirmed) setStudioStep("export");
    },
    [isConfirmed],
  );

  const workflowStep = !isConfirmed ? "review" : studioStep;
  const uiContext: AgentUiContext = {
    page: "resume-agent",
    step: workflowStep,
    focus: uiFocus,
  };

  const studioContent = !hasProfile ? (
    <div className="flex h-full min-h-[360px] flex-col justify-center p-4 sm:p-6">
      <ProfileUploader
        hasProfile={false}
        onUploaded={(p) => {
          setProfile(p);
          setLoadError(null);
          setHasElevatePreview(false);
          setHasExported(false);
          setExportCtx(null);
          setStudioStep("review");
        }}
      />
      <p className="mt-6 text-center text-sm text-slate-500">
        上传后左侧编辑核对，确认后解锁优化预览；右侧 Agent 协助改稿。
      </p>
    </div>
  ) : (
    <ResumeStudio
      profile={profile!}
      isConfirmed={isConfirmed}
      canExport={canExport}
      activeStep={studioStep}
      generateTick={generateTick}
      onElevateBusyChange={setElevateBusy}
      onProfileChange={(p) => {
        setProfile(p);
      }}
      onElevateLoaded={(info) => {
        setHasElevatePreview(true);
        setExportCtx(info);
      }}
      onExported={() => setHasExported(true)}
      jobId={jobId}
      uiContext={uiContext}
      onUiFocus={setUiFocus}
    />
  );

  return (
    <>
      <MergeConflictBanner />

      <div className="flex min-h-0 flex-1 flex-col gap-2">
        {loading ? <p className="shrink-0 text-sm text-slate-500">加载登录态…</p> : null}
        {loadError ? (
          <p className="shrink-0 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-700">{loadError}</p>
        ) : null}
        <SystemStatusBanner profile={profile} />

        <AgentWorkbench
          layout="split"
          pageKey="resume-agent"
          title="简历优化"
          profileId={profileId}
          jobId={jobId}
          skillHint="resume-coach"
          kind="resume"
          disabled={!isUser}
          placeholder="例如：华为那段写具体一点；把 Docker 职责拆成三条"
          headerExtra={
            <WorkflowHeader
              steps={steps}
              profile={profile}
              onStepClick={handleStepClick}
              onReopened={(p) => {
                setProfile(p);
                setStudioStep("review");
                setHasElevatePreview(false);
                setExportCtx(null);
              }}
              profileSwitch={
                <ProfileSwitcher
                  onSwitched={() => {
                    void refresh();
                  }}
                />
              }
              trailing={
                hasProfile ? (
                  <ResumeWorkflowActions
                    step={workflowStep}
                    profile={profile}
                    isConfirmed={isConfirmed}
                    canExport={canExport}
                    hasElevatePreview={hasElevatePreview}
                    elevateBusy={elevateBusy}
                    onProfileChange={(p) => {
                      setProfile(p);
                    }}
                    onStepChange={setStudioStep}
                    onGeneratePreview={() => setGenerateTick((t) => t + 1)}
                    onExported={() => setHasExported(true)}
                    exportCtx={exportCtx}
                  />
                ) : null
              }
            />
          }
          onProfileUpdated={reloadProfile}
          uiContext={uiContext}
          studio={studioContent}
        />
      </div>
    </>
  );
}

export default function ResumeAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-slate-500">加载中…</p>}>
      <ResumeAgentInner />
    </Suspense>
  );
}
