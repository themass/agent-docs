import { apiJson } from "./client";

export type ResumeDraft = {
  id: string;
  profile_id: string;
  elevation_level: string;
  sections: Record<string, unknown>;
  elevation_map: Array<Record<string, unknown>>;
};

export type ElevatePreview = {
  draft: ResumeDraft;
  html: string;
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

export function getElevatePreview(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
  locale: ResumeTrack = "zh-CN",
  jobId?: string,
): Promise<ElevatePreview> {
  const jobQ = jobId ? `&job_id=${encodeURIComponent(jobId)}` : "";
  return apiJson<ElevatePreview>(
    `/profiles/${profileId}/elevate/preview?elevation_level=${elevationLevel}&locale=${locale}${jobQ}`,
  );
}

export function exportProfile(
  profileId: string,
  format: "pdf" | "docx" = "pdf",
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

export type ExportReview = {
  draft_id: string;
  status: string;
  notes: string | null;
  issues: ReviewIssue[];
  can_export: boolean;
};

export function reviewBeforeExport(
  profileId: string,
  elevationLevel: "conservative" | "standard" | "elevated" = "elevated",
  locale: ResumeTrack = "zh-CN",
  draftId?: string | null,
): Promise<ExportReview> {
  const draftQ = draftId ? `&draft_id=${encodeURIComponent(draftId)}` : "";
  return apiJson<ExportReview>(
    `/profiles/${profileId}/export/review?elevation_level=${elevationLevel}&locale=${locale}${draftQ}`,
  );
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
