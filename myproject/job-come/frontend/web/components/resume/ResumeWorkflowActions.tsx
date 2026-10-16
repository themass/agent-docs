"use client";

import { userFacingApiError } from "@/lib/api/user-error";

import { useState } from "react";

import { confirmProfile, getProfile, type Profile } from "@/lib/api/profile";
import type { StudioStep } from "@/lib/resume-workflow";


type Props = {
  step: StudioStep;
  profile: Profile | null;
  isConfirmed: boolean;
  hasElevatePreview: boolean;
  elevateBusy?: boolean;
  onProfileChange: (profile: Profile) => void;
  onStepChange: (step: StudioStep) => void;
  onGeneratePreview?: () => void;
};

/** Compact primary actions aligned with the step row. */
export function ResumeWorkflowActions({
  step,
  profile,
  isConfirmed,
  hasElevatePreview,
  elevateBusy = false,
  onProfileChange,
  onStepChange,
  onGeneratePreview,
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
      <div className="flex shrink-0 items-center gap-1.5">
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
          className="btn btn-sm btn-primary"
          title={hasElevatePreview ? undefined : "先生成一份优化稿"}
        >
          下一步：导出
        </button>
      </div>
    );
  }

  // Step 4 owns the check and the downloads inside the page itself; the toolbar
  // only offers the way back so the two steps never present the same control.
  if (step === "export" && isConfirmed) {
    return (
      <div className="flex shrink-0 items-center gap-1.5">
        <button
          type="button"
          onClick={() => onStepChange("elevate")}
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
        onClick={() => onStepChange("elevate")}
        className="btn btn-sm btn-primary"
      >
        进入优化预览
      </button>
    );
  }

  return null;
}
