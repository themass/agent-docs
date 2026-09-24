import type { Profile } from "@/lib/api/profile";

export type StudioStep = "review" | "elevate" | "export";

export type WorkflowStep = {
  id: "upload" | "review" | "elevate" | "export";
  label: string;
  done: boolean;
  active: boolean;
  disabled?: boolean;
};

type WorkflowState = {
  hasElevatePreview: boolean;
  hasExported: boolean;
  currentStep?: StudioStep;
};

export function computeWorkflowSteps(
  profile: Profile | null,
  state: WorkflowState,
): WorkflowStep[] {
  const hasProfile = Boolean(profile);
  const isConfirmed = profile?.status === "confirmed";
  const canElevate = isConfirmed;
  const canExport = isConfirmed;

  const uploadDone = hasProfile;
  const reviewDone = isConfirmed;
  const elevateDone = state.hasElevatePreview;
  const exportDone = state.hasExported;

  const current = state.currentStep;
  const activeId: WorkflowStep["id"] = !hasProfile
    ? "upload"
    : current === "review" || current === "elevate" || current === "export"
      ? current
      : !reviewDone
        ? "review"
        : "elevate";

  return [
    { id: "upload", label: "上传解析", done: uploadDone, active: activeId === "upload" },
    {
      id: "review",
      label: "核对确认",
      done: reviewDone,
      active: activeId === "review",
      disabled: !hasProfile,
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
    },
  ];
}

export function isDegradedIngest(profile: Profile | null): boolean {
  const mode = profile?.payload.meta?.ingest_mode;
  return mode === "mock_fallback" || mode === "mock_no_text";
}
