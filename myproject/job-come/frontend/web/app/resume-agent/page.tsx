"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AgentWorkbench } from "@/components/agent/AgentWorkbench";
import { MergeConflictBanner } from "@/components/auth/MergeConflictBanner";
import { ProfileSwitcher } from "@/components/profile/ProfileSwitcher";
import { ProfileUploader, type StartMode } from "@/components/profile/ProfileUploader";
import { WorkflowHeader } from "@/components/profile/WorkflowHeader";
import { ResumeStudio } from "@/components/resume/ResumeStudio";
import type { ElevationLevel } from "@/components/resume/ElevatePreviewPanel";
import { ResumeWorkflowActions } from "@/components/resume/ResumeWorkflowActions";
import { getProfile, type Profile } from "@/lib/api/profile";
import { isProfileParseInFlight } from "@/lib/profile-parse";
import { useProfileDraft } from "@/lib/hooks/useProfileDraft";
import { useProfileParsePoll } from "@/lib/hooks/useProfileParsePoll";
import type { ResumeTrack } from "@/lib/api/resume";
import {
  computeWorkflowSteps,
  profilePastUploadStep,
  type StudioStep,
  type WorkflowStep,
} from "@/lib/resume-workflow";
import type { AgentUiContext, AgentUiFocus } from "@/lib/ui-context";
import { useAuth } from "@/lib/auth/AuthProvider";
import { ZHOUKA_NAME } from "@/lib/brand";

/**
 * The first turn when a user starts from nothing and chose to talk rather than fill in
 * a form. Written as the user's own request so the agent's interview skill picks it up
 * the same way it would a typed one — and so the transcript reads correctly on replay.
 */
const BUILD_BY_CHAT_OPENER =
  "我手上没有简历，想从零开始建一份。请一次问我一个问题，" +
  "先问我最近这份工作做什么、负责多大范围，再逐步往下挖具体成果和数字。";

function ResumeAgentInner() {
  const { context, loading, refresh } = useAuth();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job_id");
  const [profile, setProfile] = useState<Profile | null>(null);
  const editor = useProfileDraft(profile, setProfile);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [hasElevatePreview, setHasElevatePreview] = useState(false);
  const [hasExported, setHasExported] = useState(false);
  const [studioStep, setStudioStep] = useState<StudioStep>("review");
  const [generateTick, setGenerateTick] = useState(0);
  const [elevateBusy, setElevateBusy] = useState(false);
  // Owned here, not inside ElevatePreviewPanel, so the toolbar selector in
  // ResumeWorkflowActions and the preview panel always show the same choice — see the
  // prop doc on ElevatePreviewPanel.level for why this moved up.
  const [elevationLevel, setElevationLevel] = useState<ElevationLevel>("standard");
  const [exportCtx, setExportCtx] = useState<{
    draftId: string;
    profileVersion: number;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  } | null>(null);
  const [uiFocus, setUiFocus] = useState<AgentUiFocus | null>(null);
  // Set when the user chose "按问题逐项填写" rather than uploading, so the review step
  // opens the question panel instead of showing them an empty profile and no next action.
  const [startInInterview, setStartInInterview] = useState(false);
  // Set when they chose "和舟卡聊着写" instead. Same empty profile, different tool: the
  // agent opens the conversation rather than the user facing an empty composer and
  // having to work out what to say.
  const [agentAutoStart, setAgentAutoStart] = useState<{ id: string; message: string } | null>(
    null,
  );
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
    let active = true;
    void getProfile(id)
      .then((data) => {
        if (active) setProfile(data);
      })
      .catch((err) => {
        if (active) setLoadError(userFacingApiError(err, "加载失败"));
      });
    return () => {
      active = false;
    };
  }, [context?.active_profile_id]);

  useEffect(() => {
    setHasElevatePreview(false);
    setHasExported(false);
    setExportCtx(null);
    setStudioStep("review");
    setStartInInterview(false);
    setAgentAutoStart(null);
    setGenerateTick(0);
    setUiFocus(null);
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
    void getProfile(profileId)
      .then((updated) => {
        setProfile(updated);
        setExportCtx(null);
        // Step 3 shows the optimized draft, not the raw profile. Bumping the tick
        // forces a fresh elevate preview so confirmed facts appear in the document
        // the user is actually reading.
        setGenerateTick((t) => t + 1);
      })
      .catch((err) => {
        setLoadError(userFacingApiError(err, "修改已确认，但刷新简历失败，请刷新页面重试。"));
      });
  }, [profileId]);

  const parsePollError = useProfileParsePoll(profile, setProfile);

  const canExport = context?.capabilities.includes("export") ?? false;
  const isUser = context?.actor === "user";
  const hasProfile = Boolean(profile);
  const uploadComplete =
    profilePastUploadStep(profile) || startInInterview || Boolean(agentAutoStart);

  const steps = useMemo(
    () =>
      computeWorkflowSteps(profile, {
        hasElevatePreview,
        hasExported,
        currentStep: isConfirmed ? studioStep : "review",
        uploadComplete,
      }),
    [profile, hasElevatePreview, hasExported, isConfirmed, studioStep, uploadComplete],
  );

  const handleStepClick = useCallback(
    (stepId: WorkflowStep["id"]) => {
      if (stepId !== "review" && (editor.dirty || editor.busy)) {
        setLoadError("请先保存顶部提示的档案修改，再进入下一步。");
        return;
      }
      if (stepId === "review") setStudioStep("review");
      if (stepId === "elevate" && isConfirmed) setStudioStep("elevate");
      // Mirrors `computeWorkflowSteps`: step 4 needs a draft to work on.
      if (stepId === "export" && isConfirmed && hasElevatePreview) setStudioStep("export");
    },
    [isConfirmed, hasElevatePreview, editor.dirty, editor.busy],
  );

  const workflowStep = isProfileParseInFlight(profile) || !isConfirmed ? "review" : studioStep;
  const uiContext: AgentUiContext = {
    page: "resume-agent",
    step: workflowStep,
    focus: uiFocus,
  };

  const studioContent = !uploadComplete ? (
    <div className="scroll-area h-full min-h-0 overflow-y-auto p-4 pb-10 sm:p-6">
      <ProfileUploader
        hasProfile={false}
        profile={profile}
        onUploaded={(p) => {
          setProfile(p);
          setLoadError(null);
          setHasElevatePreview(false);
          setHasExported(false);
          setExportCtx(null);
          setStudioStep("review");
        }}
        onStartInterview={(p, mode: StartMode) => {
          setProfile(p);
          setLoadError(null);
          setHasElevatePreview(false);
          setHasExported(false);
          setExportCtx(null);
          setStudioStep("review");
          setStartInInterview(mode === "interview");
          setAgentAutoStart(mode === "chat" ? { id: p.id, message: BUILD_BY_CHAT_OPENER } : null);
        }}
      />
      <p className="mt-6 text-center text-sm text-ink-500">
        上传后左侧编辑核对，确认后解锁优化预览；右侧{ZHOUKA_NAME}协助改稿。
      </p>
    </div>
  ) : (
    <ResumeStudio
      profile={profile!}
      editor={editor}
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
        setHasExported(false);
      }}
      onExported={() => setHasExported(true)}
      onStepChange={setStudioStep}
      exportCtx={exportCtx}
      jobId={jobId}
      uiContext={uiContext}
      onUiFocus={setUiFocus}
      startInInterview={startInInterview}
      level={elevationLevel}
      onLevelChange={setElevationLevel}
    />
  );

  return (
    <>
      <h1 className="sr-only">舟卡 JobCome — AI 简历优化、解析与导出</h1>
      <MergeConflictBanner />

      <div className="flex min-h-0 flex-1 flex-col gap-2 [min-height:calc(100dvh-var(--header-h)-1.25rem)]">
        {loading ? <p className="shrink-0 text-sm text-ink-500">加载登录态…</p> : null}
        {loadError ? (
          <p className="shrink-0 rounded-lg bg-danger-50 px-4 py-2 text-sm text-danger-700">{loadError}</p>
        ) : null}
        {parsePollError ? (
          <p role="alert" className="shrink-0 rounded-lg bg-danger-50 px-4 py-2 text-sm text-danger-700">{parsePollError}</p>
        ) : null}
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
                  disabled={editor.dirty || editor.busy}
                  onSwitched={() => {
                    void refresh();
                  }}
                />
              }
              trailing={
                uploadComplete ? (
                  <div className="flex flex-wrap items-center justify-end gap-2">
                    <div className="flex items-center gap-2">
                      <span role="status" className="max-w-48 text-xs text-ink-600">{editor.busy ? "保存中…" : editor.draft?.conflict ? "版本冲突，编辑已保留" : editor.message ?? (editor.dirty ? "有未保存的修改" : "档案已保存")}</span>
                      <button type="button" className="btn btn-sm btn-primary" disabled={editor.busy || !editor.dirty || Boolean(editor.draft?.conflict)} onClick={() => void editor.save()}>保存修改</button>
                    </div>
                  <ResumeWorkflowActions
                    beforeContinue={editor.save}
                    step={workflowStep}
                    profile={profile}
                    isConfirmed={isConfirmed}
                    hasElevatePreview={hasElevatePreview}
                    elevateBusy={elevateBusy}
                    onProfileChange={(p) => {
                      setProfile(p);
                    }}
                    onStepChange={setStudioStep}
                    onGeneratePreview={() => setGenerateTick((t) => t + 1)}
                    level={elevationLevel}
                    onLevelChange={setElevationLevel}
                  />
                  </div>
                ) : null
              }
            />
          }
          onProfileUpdated={reloadProfile}
          uiContext={uiContext}
          autoStart={agentAutoStart}
          studio={studioContent}
        />
      </div>
    </>
  );
}

export default function ResumeAgentPage() {
  return (
    <Suspense fallback={<p className="text-sm text-ink-500">加载中…</p>}>
      <ResumeAgentInner />
    </Suspense>
  );
}
