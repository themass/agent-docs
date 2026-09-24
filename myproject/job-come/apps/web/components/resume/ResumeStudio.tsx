"use client";

import { useEffect, useState } from "react";

import { ProfileOverview } from "@/components/profile/ProfileOverview";
import { ProfileStudioEditor } from "@/components/profile/ProfileStudioEditor";
import { ProfileUploader } from "@/components/profile/ProfileUploader";
import { ElevatePreviewPanel } from "@/components/resume/ElevatePreviewPanel";
import { getProfile, type Profile } from "@/lib/api/profile";
import { localizeProfile, type ResumeTrack } from "@/lib/api/resume";
import type { StudioStep } from "@/lib/resume-workflow";

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
  jobId?: string | null;
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
  jobId = null,
}: Props) {
  const [showEditor, setShowEditor] = useState(false);

  const step = !isConfirmed ? "review" : activeStep;
  const showPreview = isConfirmed && (step === "elevate" || step === "export");

  useEffect(() => {
    if (step !== "export") return;
    document.getElementById("resume-header-export")?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [step]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-slate-50/40">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-3 p-3 sm:p-4">
          {step === "review" ? (
            <>
              <ProfileUploader
                hasProfile
                onUploaded={(p) => {
                  onProfileChange(p);
                }}
              />
              <ProfileOverview
                profile={profile}
                onRelocalize={(source) => {
                  void localizeProfile(profile.id, source)
                    .then(() => getProfile(profile.id))
                    .then(onProfileChange)
                    .catch(() => undefined);
                }}
              />
              {!isConfirmed ? (
                <div className="rounded-xl border border-dashed border-brand-200 bg-brand-50/50 px-4 py-3 text-sm text-brand-900">
                  <p className="font-medium">当前：核对确认</p>
                  <p className="mt-1 text-brand-800/80">请检查工作经历与要点，确认按钮在顶部工具栏。</p>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-2 rounded-lg border border-emerald-200 bg-emerald-50/80 px-3 py-1.5 text-xs text-emerald-800">
                  <span className="inline-flex items-center gap-2">
                    <svg className="h-4 w-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    档案已确认 · 可在顶部进入「优化预览」
                  </span>
                  <button
                    type="button"
                    onClick={() => setShowEditor((v) => !v)}
                    className="rounded-md border border-emerald-200 bg-white px-2.5 py-1 text-[11px] font-medium text-emerald-900 hover:bg-emerald-50"
                  >
                    {showEditor ? "收起表单" : "展开表单编辑"}
                  </button>
                </div>
              )}
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-semibold text-slate-800">快速编辑</h3>
                {!isConfirmed ? (
                  <button
                    type="button"
                    onClick={() => setShowEditor((v) => !v)}
                    className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
                  >
                    {showEditor ? "收起表单" : "展开表单编辑"}
                  </button>
                ) : null}
              </div>
              {showEditor ? (
                <ProfileStudioEditor profile={profile} onSaved={onProfileChange} />
              ) : null}
            </>
          ) : null}

          {showPreview ? (
            <ElevatePreviewPanel
              profileId={profile.id}
              canExport={canExport}
              onPreviewLoaded={onElevateLoaded}
              onExported={onExported}
              autoLoad
              generateTick={generateTick}
              onBusyChange={onElevateBusyChange}
              jobId={jobId}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
