import { apiJson } from "./client";

export type JDParseResult = {
  company: string | null;
  role_title: string;
  keywords: string[];
  must_have_skills?: string[];
};

export type FitScore = {
  job_id: string | null;
  score: number;
  recommendation: "go" | "caution" | "no";
  gaps: string[];
  blockers: string[];
  summary: string | null;
  elevate_hints?: string[];
  dimensions?: Record<string, number>;
  legitimacy?: string | null;
};

export type Job = {
  id: string;
  profile_id: string;
  company: string;
  title: string;
  source_url: string | null;
  requirements: Record<string, unknown>;
  fit_score: number | null;
  fit_recommendation: string | null;
  fit_gaps: string[];
  fit_blockers: string[];
  fit_summary?: string | null;
  elevate_hints?: string[];
  fit_dimensions?: Record<string, number>;
  legitimacy?: string | null;
  parsed?: JDParseResult;
};

export function parseJob(profileId: string, rawText: string, sourceUrl?: string) {
  return apiJson<Job>(`/jobs/profiles/${profileId}/parse`, {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, source_url: sourceUrl, save: true }),
  });
}

export function parseJobUrl(profileId: string, url: string) {
  return apiJson<Job>(`/jobs/profiles/${profileId}/parse-url`, {
    method: "POST",
    body: JSON.stringify({ url, save: true }),
  });
}

export function scoreFit(profileId: string, jobId: string) {
  return apiJson<FitScore>(`/jobs/profiles/${profileId}/fit`, {
    method: "POST",
    body: JSON.stringify({ job_id: jobId }),
  });
}

export function listJobs(profileId: string) {
  return apiJson<Job[]>(`/jobs/profiles/${profileId}`);
}

export function runApplyPipeline(
  profileId: string,
  body: { job_id?: string; raw_text?: string; export_format?: "pdf" | "docx" },
) {
  return apiJson<{
    job_id: string;
    fit: FitScore;
    draft: Record<string, unknown>;
    export: Record<string, unknown> | null;
    application_id: string | null;
  }>(`/jobs/profiles/${profileId}/apply-pipeline`, {
    method: "POST",
    body: JSON.stringify({ ...body, create_application: true }),
  });
}

export type CampaignStats = {
  profile_id: string;
  phase: string;
  warmup_job_ids: string[];
  target_job_ids: string[];
  progress: Record<string, number>;
  fit_calibration: { sample_size: number; bands: Record<string, { total: number; interviewed: number }> };
};

export function getCampaignStats(profileId: string) {
  return apiJson<CampaignStats>(`/campaign/profiles/${profileId}`);
}

export type ApplicationRow = {
  id: string;
  job_id: string;
  company: string | null;
  title: string | null;
  applied_at: string | null;
  resume_variant_id: string | null;
};

export function listApplications(profileId: string) {
  return apiJson<ApplicationRow[]>(`/jobs/profiles/${profileId}/applications`);
}
