import { apiJson, API_BASE, parseApiError } from "./client";
import { readPreviewResult, type PreviewProgressEvent } from "../preview-progress";
import { readOperationResult } from "../operation-stream";
import type { ReviewProgressEvent } from "../review-progress";

export type ResumeDraft = {
  id: string;
  profile_id: string;
  profile_version: number;
  elevation_level: string;
  sections: Record<string, unknown>;
  elevation_map: Array<Record<string, unknown>>;
};

export type ElevatePreview = {
  draft: ResumeDraft;
  html: string;
  coverage?: ResumeCoverage;
  /** Length/bullet measurements. Step 3 shows only the length half; see ElevatePreviewPanel. */
  diagnostics?: ResumeDiagnostics;
  /** What the document-level pass did: section order, bullet promotions, scope lines. */
  structure?: ResumeStructure;
  /** The role family's document bar, and which parts of it this draft meets. */
  blueprint?: ResumeBlueprintReport;
};

export type ExportJob = {
  id: string;
  status: string;
  format: string;
  download_url: string | null;
  error_message: string | null;
};

export function elevateProfile(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
): Promise<ResumeDraft> {
  return apiJson<ResumeDraft>(
    `/profiles/${profileId}/elevate?elevation_level=${elevationLevel}`,
    { method: "POST" },
  );
}

export type ResumeTrack = "zh-CN" | "en-US" | "zh-en";

export async function getElevatePreview(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
  locale: ResumeTrack = "zh-CN",
  jobId?: string,
  options?: { signal?: AbortSignal; force?: boolean; onProgress?: (event: PreviewProgressEvent) => void },
): Promise<ElevatePreview> {
  const jobQ = jobId ? `&job_id=${encodeURIComponent(jobId)}` : "";
  const forceQ = options?.force ? "&force=1" : "";
  const response = await fetch(
    `${API_BASE}/profiles/${profileId}/elevate/preview/stream?elevation_level=${elevationLevel}&locale=${locale}${jobQ}${forceQ}`,
    { signal: options?.signal, credentials: "include", headers: { Accept: "text/event-stream" } },
  );
  if (!response.ok) throw await parseApiError(response);
  return readPreviewResult<ElevatePreview>(response, options?.onProgress);
}

export type ExportFormat = "pdf" | "docx" | "html";

export function exportProfile(
  profileId: string,
  format: ExportFormat = "pdf",
  options?: {
    locale?: ResumeTrack;
    templateId?: string;
    elevationLevel?: "conservative" | "standard" | "elevated";
    draftId?: string;
  },
): Promise<ExportJob> {
  const locale = options?.locale ?? "zh-CN";
  return apiJson<ExportJob>(`/profiles/${profileId}/export`, {
    method: "POST",
    body: JSON.stringify({
      format,
      elevation_level: options?.elevationLevel ?? "elevated",
      locale,
      template_id: options?.templateId,
      draft_id: options?.draftId,
    }),
  });
}

export type ReviewIssue = {
  severity?: string;
  field?: string;
  message?: string;
  code?: string;
};

/** Deterministic screening measurements; advisory only, never gates export. */
export type ResumeDiagnostics = {
  estimated_pages: number;
  total_chars: number;
  bullet_count: number;
  longest_bullet_chars: number;
  keyword_coverage: {
    total: number;
    present: number;
    missing: string[];
    skills_only: string[];
  };
  notes: string[];
};

/** One source accomplishment with no recognisable counterpart in the draft. */
export type DroppedHighlight = {
  where: string;
  text: string;
  origin: "experience" | "project";
  best_match: number;
};

/**
 * Did the written resume keep what the profile contains? Measured, advisory only —
 * merging two highlights that describe the same work is legitimate, so the call stays
 * with the user.
 */
export type ResumeCoverage = {
  source_highlights: number;
  covered: number;
  draft_bullets: number;
  ratio: number;
  projects_missing: boolean;
  dropped: DroppedHighlight[];
  notes: string[];
};

export type ExportReview = {
  draft_id: string;
  /**
   * `passed` | `failed` | `unavailable`.
   *
   * `unavailable` is not a verdict about the resume -- the reviewer never reached one
   * (gateway down, LLM off, unreadable response). It must not be presented as a
   * finding, and it is never a reason to withhold a download.
   */
  status: string;
  notes: string | null;
  issues: ReviewIssue[];
  /** False when `status === "unavailable"`. */
  reviewed?: boolean;
  /** Findings above `warning`. Advisory: they are acknowledged, not enforced. */
  blocking_issue_count?: number;
  /** Always true. Retained for contract stability; the UI gates on acknowledgement. */
  can_export: boolean;
  diagnostics?: ResumeDiagnostics;
  coverage?: ResumeCoverage;
};

export async function reviewBeforeExport(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
  locale: ResumeTrack = "zh-CN",
  draftId?: string | null,
  options?: { signal?: AbortSignal; onProgress?: (event: ReviewProgressEvent) => void },
): Promise<ExportReview> {
  const draftQ = draftId ? `&draft_id=${encodeURIComponent(draftId)}` : "";
  const response = await fetch(
    `${API_BASE}/profiles/${profileId}/export/review/stream?elevation_level=${elevationLevel}&locale=${locale}${draftQ}`,
    { signal: options?.signal, credentials: "include", headers: { Accept: "text/event-stream" } },
  );
  if (!response.ok) throw await parseApiError(response);
  return readOperationResult<ExportReview, ReviewProgressEvent>(response, options?.onProgress);
}

export type TrackState = {
  status: string;
  draft_id?: string | null;
  reviewer_status?: string | null;
  reason?: string | null;
};

export type ResumeTracksResponse = {
  source_locale: string;
  tracks: {
    "zh-CN": TrackState;
    "en-US": TrackState;
    "zh-en": TrackState;
  };
};

export function listResumeTracks(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
): Promise<ResumeTracksResponse> {
  return apiJson<ResumeTracksResponse>(
    `/profiles/${profileId}/resume-tracks?elevation_level=${elevationLevel}`,
  );
}

export function localizeProfile(
  profileId: string,
  sourceLocale?: "zh-CN" | "en-US",
): Promise<ResumeTracksResponse> {
  return apiJson<ResumeTracksResponse>(`/profiles/${profileId}/localize`, {
    method: "POST",
    body: JSON.stringify({ source_locale: sourceLocale ?? null }),
  });
}


/** One bullet the structure pass moved inside its block. */
export type BulletMove = {
  field_path: string;
  where: string;
  text: string;
  from_index: number;
  to_index: number;
  reason: string;
};

/** Whether the 摘要 reads conclusion-first. All four parts are measured, not guessed. */
export type SummaryShape = {
  present: boolean;
  positioning: boolean;
  evidence: boolean;
  direction: boolean;
  conclusion_first: boolean;
};

/**
 * The document-level composition result. This is the answer to "what changed beyond
 * the wording" — section order, which bullet leads each block, and how many blocks
 * open with a scope line. Without showing it, a reordered and re-framed document reads
 * as nothing but per-sentence polish.
 */
export type ResumeStructure = {
  section_order: string[];
  section_order_changed: boolean;
  section_order_reason: string | null;
  moves: BulletMove[];
  scope_lines: number;
  blocks_total: number;
  summary_shape: SummaryShape | null;
  issues: Array<{ code: string; field_path: string; message: string }>;
};

/** The written bar for one role family. Same numbers the writer prompt receives. */
export type ResumeBlueprint = {
  family: string;
  label: string;
  section_order: string[];
  summary_formula: string[];
  scope_dimensions: string[];
  evidence_ladder: string[];
  anti_patterns: string[];
  must_haves: string[];
  lead_bullets: number;
  tail_bullets: number;
  outcome_ratio: number;
  quantification_optional: boolean;
};

/** One requirement, and whether this draft meets it. */
export type BlueprintFinding = {
  id: string;
  label: string;
  why: string;
  fix: string;
  met: boolean;
  detail: string;
  field_path: string | null;
};

export type ResumeBlueprintReport = {
  blueprint: ResumeBlueprint;
  findings: BlueprintFinding[];
  met: number;
  total: number;
};
