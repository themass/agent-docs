import { apiJson } from "./client";

/**
 * Presentation levers the user controls: which audience the resume is written for,
 * and which supported fact each bullet leads with.
 *
 * These never change the facts in the profile, which is why this is a plain setter
 * with no confirmation step — unlike evidence answers (new source facts) and profile
 * patches (which require explicit user confirmation).
 */

export type RoleFamilyOption = {
  id: string;
  label: string;
  outcome_metrics: string[];
  must_haves: string[];
  quantification_optional: boolean;
};

export type FramingPresetOption = {
  id: string;
  label: string;
  hint: string;
  /** True when this angle is what a recruiter in the resolved family reads for first. */
  recommended: boolean;
};

export type WritingOptions = {
  role_family: string;
  role_label: string;
  role_family_explicit: boolean;
  quantification_optional: boolean;
  framing_emphases: string[];
  framing_explicit: boolean;
  max_emphases: number;
  families: RoleFamilyOption[];
  presets: FramingPresetOption[];
};

export function getWritingOptions(
  profileId: string,
  options?: { jobId?: string | null },
): Promise<WritingOptions> {
  const query = options?.jobId ? `?job_id=${encodeURIComponent(options.jobId)}` : "";
  return apiJson<WritingOptions>(`/profiles/${profileId}/writing-options${query}`);
}

export function updateWritingOptions(
  profileId: string,
  body: { roleFamily?: string | null; framingEmphases?: string[] | null },
  options?: { jobId?: string | null },
): Promise<WritingOptions> {
  const query = options?.jobId ? `?job_id=${encodeURIComponent(options.jobId)}` : "";
  return apiJson<WritingOptions>(`/profiles/${profileId}/writing-options${query}`, {
    method: "PUT",
    body: JSON.stringify({
      // `undefined` is omitted by JSON.stringify, which the API reads as "unchanged".
      role_family: body.roleFamily,
      framing_emphases: body.framingEmphases,
    }),
  });
}
