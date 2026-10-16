"use client";

import { useState } from "react";

import { ProfileOverview } from "@/components/profile/ProfileOverview";
import { ProfileStudioEditor } from "@/components/profile/ProfileStudioEditor";
import { ProfileUploader } from "@/components/profile/ProfileUploader";
import { ElevatePreviewPanel } from "@/components/resume/ElevatePreviewPanel";
import { EvidencePanel } from "@/components/resume/EvidencePanel";
import { ResumeExportStep } from "@/components/resume/ResumeExportStep";
import { WritingOptionsPanel } from "@/components/resume/WritingOptionsPanel";
import { getProfile, type Profile } from "@/lib/api/profile";
import { localizeProfile, type ResumeTrack } from "@/lib/api/resume";
import type { StudioStep } from "@/lib/resume-workflow";
import type { AgentUiContext, AgentUiFocus } from "@/lib/ui-context";

type Props = {
  profile: Profile;
  isConfirmed: boolean;
  canExport: boolean;
  activeStep: StudioStep;
  generateTick: number;
  onElevateBusyChange?: (busy: boolean) => void;
  onProfileChange: (profile: Profile) => void;
  onElevateLoaded: (info: {
    draftId: string;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  }) => void;
  onExported: () => void;
  onStepChange: (step: StudioStep) => void;
  exportCtx?: {
    draftId: string;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  } | null;
  jobId?: string | null;
  uiContext?: AgentUiContext | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
};

export function ResumeStudio({
  profile,
  isConfirmed,
  canExport,
  activeStep,
  generateTick,
  onElevateBusyChange,
  onProfileChange,
  onElevateLoaded,
  onExported,
  onStepChange,
  exportCtx = null,
  jobId = null,
  uiContext = null,
  onUiFocus,
}: Props) {
  const [showEditor, setShowEditor] = useState(false);
  // Answering evidence questions changes the source facts, so the draft on screen is
  // stale the moment they are saved. Bumping this re-runs generation with the new facts.
  const [evidenceTick, setEvidenceTick] = useState(0);
  // Changing the role family or framing angle changes how the same facts are written,
  // so the draft is stale too — and the evidence questions themselves are derived per
  // family, so they have to be re-fetched rather than just re-rendered.
  const [optionsTick, setOptionsTick] = useState(0);

  const step = !isConfirmed ? "review" : activeStep;

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface-sunken">
      <div className="scroll-area min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-3 p-3 sm:p-4">
          {step === "review" ? (
            <>
              <ProfileUploader
                hasProfile
                profile={profile}
                onUploaded={(p) => {
                  onProfileChange(p);
                }}
              />
              <ProfileOverview
                profile={profile}
                uiContext={uiContext}
                onUiFocus={onUiFocus}
                onRelocalize={(source) => {
                  void localizeProfile(profile.id, source)
                    .then(() => getProfile(profile.id))
                    .then(onProfileChange)
                    .catch(() => undefined);
                }}
              />
              {!isConfirmed ? (
                <div className="notice notice-info">
                  <div>
                    <p className="font-medium">当前：核对确认</p>
                    <p className="mt-0.5 text-xs leading-relaxed opacity-80">
                      请检查工作经历与要点是否属实。确认按钮在顶部工具栏，确认后进入优化预览。
                    </p>
                  </div>
                </div>
              ) : (
                <div className="notice notice-success items-center justify-between">
                  <span className="inline-flex items-center gap-2 text-xs font-medium">
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    档案已确认 · 可在顶部进入「优化预览」
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowEditor((v) => !v)}
                    className="btn btn-sm btn-secondary shrink-0"
                  >
                    {showEditor ? "收起表单" : "展开表单编辑"}
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-ink-900">快速编辑</h3>
                {!isConfirmed ? (
                  <button
                    type="button"
                    onClick={() => setShowEditor((v) => !v)}
                    className="btn btn-sm btn-secondary"
                  >
                    {showEditor ? "收起表单" : "展开表单编辑"}
                  </button>
                ) : null}
              </div>
              {showEditor ? (
                <ProfileStudioEditor
                  profile={profile}
                  onSaved={onProfileChange}
                  focusPath={uiContext?.focus?.path}
                  onUiFocus={onUiFocus}
                />
              ) : null}
            </>
          ) : null}

          {step === "elevate" ? (
            <>
              <WritingOptionsPanel
                profileId={profile.id}
                jobId={jobId}
                onChanged={() => setOptionsTick((n) => n + 1)}
              />
              <EvidencePanel
                profileId={profile.id}
                jobId={jobId}
                reloadTick={optionsTick}
                onAnswersSaved={(stored) => {
                  if (stored <= 0) return;
                  void getProfile(profile.id).then(onProfileChange).catch(() => undefined);
                  setEvidenceTick((n) => n + 1);
                }}
              />
              <ElevatePreviewPanel
                profileId={profile.id}
                canExport={canExport}
                onPreviewLoaded={onElevateLoaded}
                onExported={onExported}
                autoLoad
                generateTick={generateTick + evidenceTick + optionsTick}
                onBusyChange={onElevateBusyChange}
                jobId={jobId}
                focusPath={uiContext?.focus?.path}
                onUiFocus={onUiFocus}
                onGoToExport={() => onStepChange("export")}
              />
            </>
          ) : null}

          {step === "export" ? (
            <ResumeExportStep
              profileId={profile.id}
              canExport={canExport}
              locale={exportCtx?.locale ?? "zh-CN"}
              elevationLevel={exportCtx?.level ?? "standard"}
              draftId={exportCtx?.draftId ?? null}
              onExported={onExported}
              onBackToElevate={() => onStepChange("elevate")}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
