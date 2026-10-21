/** Completed stages reflect server work, not elapsed-time estimates. */
export const REVIEW_STAGES = [
  { id: "read", label: "读取档案与预览稿" },
  { id: "rules", label: "检查覆盖与篇幅" },
  { id: "model", label: "模型核对事实与表达" },
  { id: "save", label: "保存质检结果" },
] as const;
export type ReviewStage = (typeof REVIEW_STAGES)[number]["id"];
export type ReviewProgress = Partial<Record<ReviewStage, "running" | "done" | "unavailable">>;
export type ReviewProgressEvent = {
  type: "progress"; stage: ReviewStage; status: "running" | "done" | "unavailable"; message?: string | null;
};
export const REVIEW_TIMEOUT_MS = 180_000;
export function advanceReviewProgress(state: ReviewProgress, event: ReviewProgressEvent): ReviewProgress {
  if (!REVIEW_STAGES.some(s => s.id === event.stage) ||
      !["running", "done", "unavailable"].includes(event.status)) return state;
  if (state[event.stage] === "done" || state[event.stage] === "unavailable") return state;
  return { ...state, [event.stage]: event.status };
}
