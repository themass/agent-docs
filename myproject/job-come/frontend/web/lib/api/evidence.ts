import { apiJson } from "./client";

/**
 * A fillable way to quantify one bullet.
 *
 * `skeleton` always contains `___` where the figure goes, and the server never fills
 * those in: a pre-filled number would be a fabricated fact the user accepts because it
 * looks plausible. Clicking a candidate inserts the skeleton for the user to complete.
 */
export type MetricCandidate = {
  dimension: string;
  unit: string;
  /** `down` | `up` | `scale` | `self` | `unknown` — which way the achievement runs. */
  direction: string;
  skeleton: string;
};

/** One question whose answer would make a specific bullet provable. */
export type EvidenceGap = {
  field_path: string;
  kind: string;
  source_text: string;
  question: string;
  examples: string[];
  weight: number;
  answer: string | null;
  /** Empty for the gap kinds whose answer is a sentence rather than a figure. */
  metrics?: MetricCandidate[];
};

export type RoleFamilyOption = {
  id: string;
  label: string;
  outcome_metrics: string[];
  must_haves: string[];
  quantification_optional: boolean;
};

export type EvidenceGapsResponse = {
  role_family: string;
  role_label: string;
  quantification_optional: boolean;
  gaps: EvidenceGap[];
  answered_count: number;
  families: RoleFamilyOption[];
};

export type EvidenceAnswerInput = {
  field_path: string;
  question: string;
  answer: string;
  kind?: string | null;
};

export type EvidenceAnswerResponse = {
  profile_id: string;
  version: number;
  stored: number;
  role_family: string;
};

export function listEvidenceGaps(
  profileId: string,
  options?: { jobId?: string | null; limit?: number },
): Promise<EvidenceGapsResponse> {
  const params = new URLSearchParams();
  if (options?.jobId) params.set("job_id", options.jobId);
  if (options?.limit) params.set("limit", String(options.limit));
  const query = params.toString();
  return apiJson<EvidenceGapsResponse>(
    `/profiles/${profileId}/evidence-gaps${query ? `?${query}` : ""}`,
  );
}

/**
 * Appends user-written facts. The role family is deliberately not sent: answering a
 * question is not a statement about the target role. `updateWritingOptions` owns it.
 */
export function submitEvidenceAnswers(
  profileId: string,
  answers: EvidenceAnswerInput[],
): Promise<EvidenceAnswerResponse> {
  return apiJson<EvidenceAnswerResponse>(`/profiles/${profileId}/evidence-answers`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
}

/** Human-readable reason each question is being asked. */
export const GAP_KIND_LABELS: Record<string, string> = {
  vague_quantity: "换成真实数字",
  weak_ownership: "说清你的角色",
  thin_bullet: "内容过短",
  missing_outcome: "缺少结果",
  unquantified_outcome: "结果缺量级",
  empty_experience: "这段还没写内容",
  empty_project: "项目只有名字",
  missing_must_have: "这个岗位必备",
};
