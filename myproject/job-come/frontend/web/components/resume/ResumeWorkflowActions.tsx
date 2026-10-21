"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useState } from "react";

import { confirmProfile, getProfile, type Profile } from "@/lib/api/profile";
import type { ElevationLevel } from "@/components/resume/ElevatePreviewPanel";
import { LEVEL_GUIDE } from "@/lib/elevation-techniques";
import { isProfileParseBlocking } from "@/lib/profile-parse";
import type { StudioStep } from "@/lib/resume-workflow";

const LEVELS: ElevationLevel[] = ["conservative", "standard", "elevated"];

type Props = {
  beforeContinue?: () => Promise<boolean>;
  step: StudioStep;
  profile: Profile | null;
  isConfirmed: boolean;
  hasElevatePreview: boolean;
  elevateBusy?: boolean;
  onProfileChange: (profile: Profile) => void;
  onStepChange: (step: StudioStep) => void;
  onGeneratePreview?: () => void;
  /**
   * The one choice that has to survive at any screen width: on a narrow split with the
   * 舟卡 chat open, the rail's own copy of this control collapses below the resume (see
   * `ElevatePreviewPanel`'s `level` prop doc) and the user cannot find it without
   * scrolling past the whole document. The toolbar never collapses, so the control
   * lives here too; the rail still explains what each level does.
   */
  level?: ElevationLevel;
  onLevelChange?: (level: ElevationLevel) => void;
};

/** Compact primary actions aligned with the step row. */
export function ResumeWorkflowActions({
  beforeContinue,
  step,
  profile,
  isConfirmed,
  hasElevatePreview,
  elevateBusy = false,
  onProfileChange,
  onStepChange,
  onGeneratePreview,
  level,
  onLevelChange,
}: Props) {
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  if (!profile || isProfileParseBlocking(profile)) return null;

  async function handleConfirm() {
    if (!profile || profile.status === "confirmed") return;
    setConfirmBusy(true);
    setConfirmError(null);
    try {
      if (beforeContinue && !(await beforeContinue())) {
        setConfirmError("修改尚未保存，请先处理保存提示。未确认档案。");
        return;
      }
      await confirmProfile(profile.id);
      const next = await getProfile(profile.id);
      onProfileChange(next);
      onStepChange("elevate");
    } catch (err) {
      setConfirmError(userFacingApiError(err, "确认失败"));
    } finally {
      setConfirmBusy(false);
    }
  }

  if (step === "review" && !isConfirmed) {
    return (
      <div className="flex shrink-0 items-center gap-1.5">
        {confirmError ? <span className="max-w-[12rem] truncate text-xs text-danger-700" title={confirmError}>
            {confirmError}
          </span> : null}
        <button
          type="button"
          onClick={() => void handleConfirm()}
          disabled={confirmBusy}
          className="btn btn-sm btn-primary"
        >
          {confirmBusy ? "确认中…" : "确认档案"}
        </button>
      </div>
    );
  }

  // Step 3 owns content only. Generating a draft and declaring it final are the
  // only two actions here; everything about files lives in step 4.
  if (step === "elevate" && isConfirmed) {
    return (
      <div className="flex shrink-0 flex-nowrap items-center gap-1.5">
        {level && onLevelChange ? (
          <div className="segment shrink-0" title="优化强度：决定措辞离原文多远">
            {LEVELS.map((id) => {
              const active = level === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => onLevelChange(id)}
                  aria-pressed={active}
                  className={`segment-item ${active ? "segment-item-active" : ""}`}
                  title={LEVEL_GUIDE[id].summary}
                >
                  {LEVEL_GUIDE[id].label}
                </button>
              );
            })}
          </div>
        ) : null}
        <button
          type="button"
          onClick={onGeneratePreview}
          disabled={elevateBusy}
          className="btn btn-sm btn-secondary"
        >
          {elevateBusy ? "生成中…" : hasElevatePreview ? "重新生成" : "生成预览"}
        </button>
        <button
          type="button"
          onClick={() => onStepChange("export")}
          disabled={!hasElevatePreview || elevateBusy}
          className="btn btn-sm btn-primary shrink-0"
          title={hasElevatePreview ? undefined : "先生成一份优化稿"}
        >
          <span className="sm:hidden">导出</span>
          <span className="hidden sm:inline">下一步：导出</span>
        </button>
      </div>
    );
  }

  // Step 4 reuses the content check and owns downloads; the toolbar
  // only offers the way back so the two steps never present the same control.
  if (step === "export" && isConfirmed) {
    return (
      <div className="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={async () => { if (!beforeContinue || await beforeContinue()) onStepChange("elevate"); }}
          className="btn btn-sm btn-secondary"
        >
          返回修改内容
        </button>
      </div>
    );
  }

  if (step === "review" && isConfirmed) {
    return (
      <button
        type="button"
        onClick={async () => { if (!beforeContinue || await beforeContinue()) onStepChange("elevate"); }}
        className="btn btn-sm btn-primary"
      >
        进入优化预览
      </button>
    );
  }

  return null;
}
