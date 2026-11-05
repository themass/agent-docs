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
  /** Null for a session created before levels existed. */
  level?: MockLevel | null;
  bank_draw_count: number;
  generated_count: number;
  questions: MockSessionQuestion[];
};

export type MockKind = "warmup" | "full";
export type MockStyle = "gentle" | "standard" | "pressure" | "deep";
export type MockLevel = "junior" | "mid" | "senior" | "expert";

export type LevelOption = {
  key: MockLevel;
  label: string;
  /** The P-series level it is compared with. A comparison, not an Alibaba standard. */
  benchmark: string;
  years: string;
  requirement: string;
};

export type LevelRecommendation = {
  recommended: MockLevel | null;
  years: number | null;
  reason: string | null;
  levels: LevelOption[];
};

export function getLevelRecommendation(profileId: string): Promise<LevelRecommendation> {
  return apiJson(`/coach/mock/level-recommendation?profile_id=${encodeURIComponent(profileId)}`);
}

export function createMockSession(body: {
  profile_id: string;
  mode?: string;
  round?: string | null;
  job_id?: string | null;
  kind?: MockKind;
  style?: MockStyle;
  level?: MockLevel;
}): Promise<MockSession> {
  return apiJson("/coach/mock/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getMockSession(sessionId: string): Promise<MockSession> {
  return apiJson(`/coach/mock/sessions/${sessionId}`);
}

export type MockReportFix = { severity: "must" | "suggest" | "nit"; text: string };

export type MockReportReference = {
  text: string;
  source: string | null;
  status: "sourced" | "pending";
};

export type MockReportQuestion = {
  question_id: string;
  stem: string;
  answer: string;
  scores: Record<string, number | null>;
  evidence: Record<string, string>;
  praise: string | null;
  fixes: MockReportFix[];
  reference: MockReportReference[];
};

/** The independent reviewer's report. Scores and averages are computed by the server. */
export type MockReport = {
  mock_session_id: string;
  /** pending: queued or being generated. failed: the review produced nothing (see can_retry). */
  status: "active" | "pending" | "failed" | "ready";
  /** Only meaningful when failed: the user may ask for the report again. */
  can_retry: boolean;
  style: string | null;
  started_at: string;
  completed_at: string | null;
  ended_reason: string | null;
  ended_early: boolean;
  message: string | null;
  overall: Record<string, number | null>;
  checks: { rejected_evidence?: number; pending_facts?: number };
  /** A warm-up's report: averages and suggestions only, no per-question detail. */
  brief: boolean;
  questions: MockReportQuestion[];
  trend: { first_five: number | null; last_five: number | null } | null;
  coverage: { total: number; asked: number; meet: number } | null;
  suggestions: MockReportSuggestion[];
};

export type MockReportSuggestion = {
  dimension: string;
  label: string;
  average: number;
  practice: string;
  question_id: string | null;
};

export type MockSessionListItem = {
  id: string;
  style: string | null;
  started_at: string;
  completed_at: string | null;
  ended_reason: string | null;
  ended_early: boolean;
  question_count: number;
  has_report: boolean;
};

export function listMockSessions(
  profileId: string,
): Promise<{ mock_sessions: MockSessionListItem[] }> {
  return apiJson(`/coach/profiles/${profileId}/mock-sessions`);
}

export function getMockReport(sessionId: string): Promise<MockReport> {
  return apiJson(`/coach/mock/sessions/${sessionId}/report`);
}

/** Put a failed report back in the queue. Refused (409) once every run has been used. */
export function retryMockReport(sessionId: string): Promise<MockReport> {
  return apiJson(`/coach/mock/sessions/${sessionId}/report/retry`, { method: "POST" });
}

export function logQuestion(
  profileId: string,
  body: {
    stem: string;
    source?: "mock" | "real";
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

export function completeMockSession(sessionId: string): Promise<MockSession> {
  return apiJson(`/coach/mock/sessions/${sessionId}/complete`, { method: "POST" });
}

export function saveInterview(profileId: string, body: {
  company: string; role_title: string; interview_date: string;
  job_id?: string | null; notes?: string; question_ids: string[];
}): Promise<{ id: string }> {
  return apiJson(`/coach/profiles/${profileId}/interviews`, {
    method: "POST", body: JSON.stringify(body),
  });
}

export type InterviewSummary = {
  id: string; company: string; role_title: string; interview_date: string;
  notes: string | null; question_ids: string[];
};
export function listInterviews(profileId: string): Promise<{ interviews: InterviewSummary[] }> {
  return apiJson(`/coach/profiles/${profileId}/interviews`);
}

/** The live map of a running session: what the interviewer has asked, and what the candidate can
 * still do on the page. Read from the same guard the interviewer uses. */
export type MockProgress = {
  style: MockStyle | null;
  status: string;
  asked_main: number;
  main_limit: number;
  remaining_main: number;
  must_have: string[];
  covered: string[];
  uncovered: string[];
  current_question_id: string | null;
  skipped: number;
  swaps_left: number;
};

export type MockActionResult = {
  accepted: boolean;
  reason: string | null;
  code: string | null;
  swaps_left: number | null;
};

export function getMockProgress(sessionId: string): Promise<MockProgress> {
  return apiJson(`/coach/mock/sessions/${sessionId}/progress`);
}

export function skipMockQuestion(sessionId: string, questionId: string): Promise<MockActionResult> {
  return apiJson(`/coach/mock/sessions/${sessionId}/skip`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId }),
  });
}

export function swapMockQuestion(sessionId: string, questionId: string): Promise<MockActionResult> {
  return apiJson(`/coach/mock/sessions/${sessionId}/swap`, {
    method: "POST",
    body: JSON.stringify({ question_id: questionId }),
  });
}
