import { apiJson } from "./client";

export type QuestionSummary = {
  id: string;
  stem: string;
  question_type: string;
  company: string | null;
  tags: unknown[];
  attempt_count: number;
  best_score?: number | null;
};

export function searchBank(
  profileId: string,
  params?: { query?: string; company?: string; limit?: number },
): Promise<{ questions: QuestionSummary[] }> {
  const q = new URLSearchParams();
  if (params?.query) q.set("query", params.query);
  if (params?.company) q.set("company", params.company);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiJson(`/coach/profiles/${profileId}/bank${qs ? `?${qs}` : ""}`);
}

export function createMockSession(body: {
  profile_id: string;
  mode?: string;
  round?: string | null;
}): Promise<{ id: string; profile_id: string; mode: string; status: string }> {
  return apiJson("/coach/mock/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type QuestionDetail = {
  id: string;
  stem: string;
  question_type: string;
  company: string | null;
  attempt_count: number;
  best_score: number | null;
  dimension_scores: Record<string, number> | null;
  attempts: Array<{
    id: string;
    user_answer: string;
    coach_feedback: Record<string, unknown> | null;
    created_at: string;
    is_best: boolean;
  }>;
};

export function getQuestionDetail(questionId: string): Promise<QuestionDetail> {
  return apiJson(`/coach/questions/${questionId}`);
}
