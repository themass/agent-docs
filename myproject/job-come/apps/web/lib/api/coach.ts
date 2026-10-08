import { apiJson } from "./client";

export type QuestionSummary = {
  id: string;
  stem: string;
  question_type: string;
  company: string | null;
  job_id?: string | null;
  tags: unknown[];
  attempt_count: number;
  best_score?: number | null;
  from_bank?: boolean;
};

export function searchBank(
  profileId: string,
  params?: { query?: string; company?: string; job_id?: string; limit?: number },
): Promise<{ questions: QuestionSummary[] }> {
  const q = new URLSearchParams();
  if (params?.query) q.set("query", params.query);
  if (params?.company) q.set("company", params.company);
  if (params?.job_id) q.set("job_id", params.job_id);
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiJson(`/coach/profiles/${profileId}/bank${qs ? `?${qs}` : ""}`);
}

export type MockSessionQuestion = {
  id: string;
  stem: string;
  from_bank: boolean;
  attempt_count: number;
};

export type MockSession = {
  id: string;
  profile_id: string;
  mode: string;
  status: string;
  round: string | null;
  job_id?: string | null;
  started_at: string;
  bank_draw_count: number;
  generated_count: number;
  questions: MockSessionQuestion[];
};

export function createMockSession(body: {
  profile_id: string;
  mode?: string;
  round?: string | null;
  job_id?: string | null;
}): Promise<MockSession> {
  return apiJson("/coach/mock/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getMockSession(sessionId: string): Promise<MockSession> {
  return apiJson(`/coach/mock/sessions/${sessionId}`);
}

export function logQuestion(
  profileId: string,
  body: {
    stem: string;
    question_type?: string;
    company?: string | null;
    role_title?: string | null;
    job_id?: string | null;
    mock_session_id?: string | null;
    round?: string | null;
    user_answer?: string | null;
  },
): Promise<QuestionSummary> {
  return apiJson(`/coach/profiles/${profileId}/questions`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type QuestionDetail = {
  id: string;
  stem: string;
  question_type: string;
  company: string | null;
  job_id?: string | null;
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
