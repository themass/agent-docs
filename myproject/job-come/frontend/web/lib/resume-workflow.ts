import type { Profile } from "@/lib/api/profile";
import { hasProfileFacts, isProfileParseBlocking } from "@/lib/profile-parse";

export type StudioStep = "review" | "elevate" | "export";

export type WorkflowStep = {
  id: "upload" | "review" | "elevate" | "export";
  label: string;
  done: boolean;
  active: boolean;
  disabled?: boolean;
  /** Shown on hover when the step is locked, so the block is self-explaining. */
  hint?: string;
};

type WorkflowState = {
  hasElevatePreview: boolean;
  hasExported: boolean;
  currentStep?: StudioStep;
  /** When the user chose「对话/逐项填写」on step 1 without uploading yet. */
  uploadComplete?: boolean;
};

/** True once the user uploaded/pasted a resume or added any profile facts (not a bare `createProfile` shell). */
export function profilePastUploadStep(profile: Profile | null): boolean {
  if (!profile) return false;
  return profile.sources?.some(source => source.parse_status === "done") || hasProfileFacts(profile);
}

export function computeWorkflowSteps(
  profile: Profile | null,
  state: WorkflowState,
): WorkflowStep[] {
  const hasProfile = Boolean(profile);
  const parsing = isProfileParseBlocking(profile);
  const pastUpload = !parsing && (state.uploadComplete ?? profilePastUploadStep(profile));
  const isConfirmed = profile?.status === "confirmed";
  const canElevate = isConfirmed && !parsing;
  // Step 4 is about turning a finished draft into files. Without a draft there is
  // nothing to check or download, so the step stays locked rather than opening an
  // empty page.
  const canExport = canElevate && state.hasElevatePreview;

  const uploadDone = pastUpload;
  const reviewDone = isConfirmed && !parsing;
  const elevateDone = state.hasElevatePreview && !parsing;
  const exportDone = state.hasExported && !parsing;

  const current = state.currentStep;
  const activeId: WorkflowStep["id"] = !hasProfile || !pastUpload
    ? "upload"
    : current === "review" || current === "elevate" || current === "export"
      ? current
      : !reviewDone
        ? "review"
        : "elevate";

  return [
    {
      id: "upload",
      label: "上传解析",
      done: uploadDone,
      active: activeId === "upload",
      disabled: uploadDone,
      hint: uploadDone ? "已完成；需要替换请在下方重新上传" : undefined,
    },
    {
      id: "review",
      label: "核对确认",
      done: reviewDone,
      active: activeId === "review",
      disabled: !hasProfile || parsing,
    },
    {
      id: "elevate",
      label: "优化预览",
      done: elevateDone,
      active: activeId === "elevate" && canElevate,
      disabled: !canElevate,
    },
    {
      id: "export",
      label: "导出",
      done: exportDone,
      active: activeId === "export" && canExport,
      disabled: !canExport,
      hint: canExport ? undefined : "先在「优化预览」生成一份优化稿",
    },
  ];
}

export function isDegradedIngest(profile: Profile | null): boolean {
  const mode = profile?.payload.meta?.ingest_mode;
  return mode === "mock_fallback" || mode === "mock_no_text";
}
