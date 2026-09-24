"use client";

import { useState } from "react";

import { confirmProfile, getProfile, type Profile } from "@/lib/api/profile";
import type { ResumeTrack } from "@/lib/api/resume";
import type { StudioStep } from "@/lib/resume-workflow";

import { ExportPanel } from "./ExportPanel";

type ExportCtx = {
  draftId: string;
  locale: ResumeTrack;
  level: "conservative" | "standard" | "elevated";
};

type Props = {
  step: StudioStep;
  profile: Profile | null;
  isConfirmed: boolean;
  canExport: boolean;
  hasElevatePreview: boolean;
  elevateBusy?: boolean;
  onProfileChange: (profile: Profile) => void;
  onStepChange: (step: StudioStep) => void;
  onGeneratePreview?: () => void;
  onExported?: () => void;
  exportCtx?: ExportCtx | null;
};

/** Compact primary actions aligned with the step row. */
export function ResumeWorkflowActions({
  step,
  profile,
  isConfirmed,
  canExport,
  hasElevatePreview,
  elevateBusy = false,
  onProfileChange,
  onStepChange,
  onGeneratePreview,
  onExported,
  exportCtx = null,
}: Props) {
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  if (!profile) return null;

  async function handleConfirm() {
    if (!profile || profile.status === "confirmed") return;
    setConfirmBusy(true);
    setConfirmError(null);
    try {
      await confirmProfile(profile.id);
      const next = await getProfile(profile.id);
      onProfileChange(next);
      onStepChange("elevate");
    } catch (err) {
      setConfirmError(err instanceof Error ? err.message : "确认失败");
    } finally {
      setConfirmBusy(false);
    }
  }

  if (step === "review" && !isConfirmed) {
    return (
      <div className="flex shrink-0 items-center gap-1.5">
        {confirmError ? <span className="max-w-[10rem] truncate text-[10px] text-red-600">{confirmError}</span> : null}
        <button
          type="button"
          onClick={() => void handleConfirm()}
          disabled={confirmBusy}
          className="rounded-md bg-brand-600 px-3 py-1 text-[11px] font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {confirmBusy ? "确认中…" : "确认档案"}
        </button>
      </div>
    );
  }

  if ((step === "elevate" || step === "export") && isConfirmed) {
    return (
      <div id="resume-header-export" className="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={onGeneratePreview}
          disabled={elevateBusy}
          className="rounded-md bg-brand-600 px-3 py-1 text-[11px] font-medium text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {elevateBusy ? "生成中…" : hasElevatePreview ? "重新生成" : "生成预览"}
        </button>
        <ExportPanel
          profileId={profile.id}
          canExport={canExport}
          onExported={onExported}
          compact
          locale={exportCtx?.locale ?? "zh-CN"}
          elevationLevel={exportCtx?.level ?? "elevated"}
          draftId={exportCtx?.draftId ?? null}
        />
      </div>
    );
  }

  if (step === "review" && isConfirmed) {
    return (
      <button
        type="button"
        onClick={() => onStepChange("elevate")}
        className="rounded-md bg-emerald-700 px-3 py-1 text-[11px] font-medium text-white hover:bg-emerald-800"
      >
        进入优化预览
      </button>
    );
  }

  return null;
}
