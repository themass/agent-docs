/** Only backend events advance a stage. Elapsed time is never a completion signal. */
export const PREVIEW_STAGES = [
  { id: "read", label: "读取最新档案与写作选项" },
  { id: "generate", label: "生成内容并保留已确认文字" },
  { id: "save", label: "保存预览稿" },
  { id: "render", label: "渲染预览" },
  { id: "audit", label: "检查内容覆盖与篇幅" },
] as const;
export type PreviewStage = (typeof PREVIEW_STAGES)[number]["id"];
export type PreviewProgress = Partial<Record<PreviewStage, "running" | "done">>;
export type PreviewProgressEvent = {
  type: "progress"; stage: PreviewStage; status: "running" | "done"; message?: string | null;
};
export function advancePreviewProgress(state: PreviewProgress, event: PreviewProgressEvent): PreviewProgress {
  if (!PREVIEW_STAGES.some((stage) => stage.id === event.stage)) return state;
  // Cached/repeated events cannot turn a completed stage back into running.
  if (state[event.stage] === "done") return state;
  return { ...state, [event.stage]: event.status };
}

import { readOperationResult } from "./operation-stream";

export function readPreviewResult<T>(
  response: Response, onProgress?: (event: PreviewProgressEvent) => void,
): Promise<T> {
  return readOperationResult<T, PreviewProgressEvent>(response, onProgress);
}
