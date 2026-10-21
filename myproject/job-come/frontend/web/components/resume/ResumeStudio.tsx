"use client";

import { isProfileParseBlocking } from "@/lib/profile-parse";
import { useState } from "react";

import { ProfileIntakePanel } from "@/components/profile/ProfileIntakePanel";
import { ProfileOverview } from "@/components/profile/ProfileOverview";
import { ProfileUploader } from "@/components/profile/ProfileUploader";
import { ElevatePreviewPanel, type ElevationLevel } from "@/components/resume/ElevatePreviewPanel";
import { EvidencePanel } from "@/components/resume/EvidencePanel";
import { ResumeQualityPanel } from "@/components/resume/ResumeQualityPanel";
import { useResumeQualityReview } from "@/lib/hooks/useResumeQualityReview";
import { ResumeExportStep } from "@/components/resume/ResumeExportStep";
import { WritingOptionsPanel } from "@/components/resume/WritingOptionsPanel";
import { getProfile, type Profile } from "@/lib/api/profile";
import { localizeProfile, type ResumeTrack } from "@/lib/api/resume";
import type { StudioStep } from "@/lib/resume-workflow";
import type { AgentUiContext, AgentUiFocus } from "@/lib/ui-context";

import type { ProfileDraftController } from "@/lib/hooks/useProfileDraft";

type Props = {
  editor: ProfileDraftController;
  profile: Profile;
  isConfirmed: boolean;
  canExport: boolean;
  activeStep: StudioStep;
  generateTick: number;
  onElevateBusyChange?: (busy: boolean) => void;
  onProfileChange: (profile: Profile) => void;
  onElevateLoaded: (info: {
    draftId: string;
    profileVersion: number;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  }) => void;
  onExported: () => void;
  onStepChange: (step: StudioStep) => void;
  exportCtx?: {
    draftId: string;
    profileVersion: number;
    locale: ResumeTrack;
    level: "conservative" | "standard" | "elevated";
  } | null;
  jobId?: string | null;
  uiContext?: AgentUiContext | null;
  onUiFocus?: (focus: AgentUiFocus) => void;
  /** The user arrived via "用对话建一份简历", so the interview opens rather than collapses. */
  startInInterview?: boolean;
  /**
   * Optimization strength, owned by the page so the toolbar selector and the preview
   * panel always agree — see the note on `ElevatePreviewPanel`'s own `level` prop.
   */
  level?: ElevationLevel;
  onLevelChange?: (level: ElevationLevel) => void;
};

export function ResumeStudio({
  editor,
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
  startInInterview = false,
  level,
  onLevelChange,
}: Props) {
  // Answering evidence questions changes the source facts, so the draft on screen is
  // stale the moment they are saved. Bumping this re-runs generation with the new facts.
  const [evidenceTick, setEvidenceTick] = useState(0);
  // Changing the role family or framing angle changes how the same facts are written,
  // so the draft is stale too — and the evidence questions themselves are derived per
  // family, so they have to be re-fetched rather than just re-rendered.
  const [optionsTick, setOptionsTick] = useState(0);
  // The blueprint checklist's "去补充证据" action has to open a panel it does not own.
  // Bumping a counter rather than lifting `expanded` keeps the panel's own open/closed
  // state local — the parent is asking it to open, not telling it what state to be in.
  const [evidenceOpenTick, setEvidenceOpenTick] = useState(0);
  // Which bullet the rail is working on, relayed to the document column so it can scroll
  // there. Held here rather than in `uiContext` because it is a transient pointer within
  // one step, not a fact about the session the agent should reason about.
  const [railFocusPath, setRailFocusPath] = useState<string | null>(null);
  // Mirrors `ElevatePreviewPanel`'s busy state locally so `WritingOptionsPanel` can show
  // "regenerating" right where the setting was changed, rather than the user having to
  // notice the toolbar's button changed to "生成中…" somewhere else on the page.
  const [elevateBusy, setElevateBusy] = useState(false);

  const quality = useResumeQualityReview({
    profileId: profile.id,
    profileVersion: profile.version,
    canReview: canExport && isConfirmed && !isProfileParseBlocking(profile)
      && exportCtx?.profileVersion === profile.version,
    draftId: exportCtx?.draftId ?? null,
    locale: exportCtx?.locale ?? "zh-CN",
    elevationLevel: exportCtx?.level ?? "standard",
  });

  // Do not show stale profile facts, confirmation banners or preview controls
  // while a replacement source is still being parsed.
  if (isProfileParseBlocking(profile)) {
    return (
      <div className="scroll-area h-full min-h-0 overflow-y-auto bg-surface-sunken p-3 sm:p-4">
        <ProfileUploader hasProfile profile={profile} onUploaded={onProfileChange} />
      </div>
    );
  }

  const step = !isConfirmed ? "review" : activeStep;

  // Step 3 is the one step whose own layout scrolls: its two columns are each bounded to
  // the pane height and scroll independently (see `.studio-columns` in globals.css). If
  // this shell also scrolled, the columns would have no height to be bounded *to* and the
  // scrollbar would move back out here, dragging both columns with one gesture — the
  // defect that arrangement exists to fix. Every other step is a single document and
  // scrolls normally.
  const stepOwnsScroll = step === "elevate";

  return (
    <div className="flex h-full min-h-0 flex-col bg-surface-sunken">
      <div
        className={
          stepOwnsScroll
            ? "min-h-0 flex-1 overflow-hidden"
            : "scroll-area min-h-0 flex-1 overflow-y-auto"
        }
      >
        <div
          className={
            stepOwnsScroll
              ? "flex h-full min-h-0 flex-col p-3 sm:p-4"
              : "space-y-3 p-3 sm:p-4"
          }
        >
          {step === "review" ? (
            <>
              <ProfileUploader
                hasProfile
                profile={profile}
                onUploaded={(p) => {
                  onProfileChange(p);
                }}
              />
              {/* The interview sits above the profile on the review step: for an empty or
                  skeleton profile it is the only thing there is to do, and for a complete
                  one it collapses to a single line. */}
              <ProfileIntakePanel
                profileId={profile.id}
                defaultOpen={startInInterview}
                onAnswered={({ stored }) => {
                  if (stored <= 0) return;
                  void getProfile(profile.id).then(onProfileChange).catch(() => undefined);
                }}
              />
              <ProfileOverview
                editor={editor}
                profile={profile}
                uiContext={uiContext}
                onUiFocus={onUiFocus}
                onProfileChange={onProfileChange}
                onRelocalize={(source) => {
                  void localizeProfile(profile.id, source)
                    .then(() => getProfile(profile.id))
                    .then(onProfileChange)
                    .catch(() => undefined);
                }}
              />
            </>
          ) : null}

          {/* Step 3's two input panels are passed *into* the preview panel as its left
              rail rather than rendered above it. Stacked above, each one pushed the
              resume further down the page until the first screen contained no resume at
              all — the exact complaint this layout answers. */}
          {step === "elevate" ? (
            <ElevatePreviewPanel
              className="min-h-0 flex-1"
              profileId={profile.id}
              profileVersion={profile.version}
              canExport={canExport}
              onPreviewLoaded={onElevateLoaded}
              onExported={onExported}
              autoLoad
              generateTick={generateTick + evidenceTick + optionsTick}
              onBusyChange={(busy) => {
                setElevateBusy(busy);
                onElevateBusyChange?.(busy);
              }}
              jobId={jobId}
              focusPath={uiContext?.focus?.path}
              onUiFocus={onUiFocus}
              onGoToExport={() => onStepChange("export")}
              onGoToEvidence={() => setEvidenceOpenTick((n) => n + 1)}
              railFocusPath={railFocusPath}
              level={level}
              onLevelChange={onLevelChange}
              rail={
                <>
                  {canExport && exportCtx?.profileVersion === profile.version && !elevateBusy ? (
                    <ResumeQualityPanel
                      quality={quality}
                      onRegenerate={() => setEvidenceTick((n) => n + 1)}
                      onEditProfile={() => onStepChange("review")}
                    />
                  ) : null}
                  <WritingOptionsPanel
                    profileId={profile.id}
                    jobId={jobId}
                    onChanged={() => setOptionsTick((n) => n + 1)}
                    regenerating={elevateBusy}
                  />
                  <EvidencePanel
                    profileId={profile.id}
                    jobId={jobId}
                    reloadTick={optionsTick}
                    openTick={evidenceOpenTick}
                    onFocusPath={setRailFocusPath}
                    onAnswersSaved={(stored) => {
                      if (stored <= 0) return;
                      void getProfile(profile.id).then(onProfileChange).catch(() => undefined);
                      setEvidenceTick((n) => n + 1);
                    }}
                  />
                </>
              }
            />
          ) : null}

          {step === "export" ? (
            <ResumeExportStep
              quality={quality}
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
