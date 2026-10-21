import type { Profile, ProfileSource } from "@/lib/api/profile";

/** Poll interval while waiting for background resume parse. */
export const PROFILE_PARSE_POLL_MS = 5000;

const PARSE_STEPS = [
  { label: "已收到简历" },
  { label: "读取文档内容" },
  { label: "提炼经历与技能" },
  { label: "生成档案草稿" },
] as const;

export type ParseProgressState = {
  currentStep: number;
  currentLabel: string;
  steps: typeof PARSE_STEPS;
};

export function isSourceParseSettled(status: string | undefined): boolean {
  const s = (status ?? "").toLowerCase();
  return s === "done" || s === "failed";
}

export function latestProfileSource(profile: Profile | null | undefined): ProfileSource | undefined {
  return profile?.sources?.reduce<ProfileSource | undefined>((latest, source) => {
    if (!latest) return source;
    const timestamp = Date.parse(source.created_at ?? "");
    const previous = Date.parse(latest.created_at ?? "");
    return Number.isFinite(timestamp) && (!Number.isFinite(previous) || timestamp > previous)
      ? source : latest;
  }, undefined);
}

export function isProfileParseInFlight(profile: Profile | null | undefined): boolean {
  const source = latestProfileSource(profile);
  if (!source) return false;
  return !isSourceParseSettled(source.parse_status);
}

/** Facts are independent of upload records: a failed source is not a profile. */
export function hasProfileFacts(profile: Profile | null | undefined): boolean {
  const payload = profile?.payload;
  return Boolean(
    payload?.contact?.name?.trim() || payload?.contact?.email?.trim() ||
    payload?.contact?.phone?.trim() || payload?.summary?.trim() ||
    payload?.experiences?.length || payload?.education?.length ||
    payload?.projects?.length || payload?.skills?.length,
  );
}

/** A failed replacement may keep the old facts; a failed first upload cannot be confirmed. */
export function isProfileParseBlocking(profile: Profile | null | undefined): boolean {
  return isProfileParseInFlight(profile) || (
    latestProfileSource(profile)?.parse_status === "failed" && !hasProfileFacts(profile)
  );
}

/** Maps backend phases to user-facing status without exposing model/provider implementation details. */
export function parseProgressState(phase: string | null | undefined): ParseProgressState {
  const key = (phase ?? "").toLowerCase();

  if (key === "queued") return { currentStep: 0, currentLabel: "已收到简历，等待开始处理", steps: PARSE_STEPS };
  if (key === "load_file" || key === "classify") {
    return { currentStep: 1, currentLabel: "正在读取文档内容", steps: PARSE_STEPS };
  }
  if (key === "inspect_document") {
    return { currentStep: 1, currentLabel: "正在判断文字是否完整，选择解析方式", steps: PARSE_STEPS };
  }
  if (key === "extract_markdown") {
    return { currentStep: 1, currentLabel: "正在尝试另一种本地文字提取方式", steps: PARSE_STEPS };
  }
  if (key.startsWith("llm_vision_")) {
    return { currentStep: 2, currentLabel: "正在识别扫描内容并整理档案", steps: PARSE_STEPS };
  }
  if (key === "extract_text") {
    return { currentStep: 1, currentLabel: "正在提取文档文字与结构", steps: PARSE_STEPS };
  }
  if (
    key === "llm_text_docx" ||
    key === "llm_text_pdf" ||
    key === "llm_text_plain" ||
    key === "llm_text" ||
    key === "llm_markitdown_pdf" ||
    key === "llm_markitdown_docx" ||
    key === "llm_vision_docx" ||
    key === "llm_vision_pdf" ||
    key === "llm_vision_image"
  ) {
    return { currentStep: 2, currentLabel: "正在提炼经历、项目与技能", steps: PARSE_STEPS };
  }
  if (key === "pick_best") {
    return { currentStep: 3, currentLabel: "正在生成可编辑档案草稿", steps: PARSE_STEPS };
  }
  return { currentStep: 1, currentLabel: "正在读取并整理简历内容", steps: PARSE_STEPS };
}

export function parsePhaseLabel(phase: string | null | undefined): string {
  if ((phase ?? "").toLowerCase() === "failed") return "解析失败";
  return parseProgressState(phase).currentLabel;
}

export function parseWaitSeconds(source: ProfileSource | undefined): number | null {
  if (!source?.created_at) return null;
  const started = Date.parse(source.created_at);
  if (Number.isNaN(started)) return null;
  return Math.max(0, Math.floor((Date.now() - started) / 1000));
}
