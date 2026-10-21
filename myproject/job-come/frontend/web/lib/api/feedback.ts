import { apiJson } from "./client";

export type FeedbackCategory = "bug" | "feature" | "question" | "other";
export type FeedbackStatus = "open" | "replying" | "resolved" | "closed";
export type FeedbackMessageRole = "user" | "admin";

export type FeedbackMessageItem = {
  id: string;
  role: FeedbackMessageRole;
  body: string;
  created_at: string;
};

export type FeedbackThreadItem = {
  id: string;
  title: string;
  category: FeedbackCategory;
  status: FeedbackStatus;
  last_message_role: FeedbackMessageRole;
  last_message_at: string;
  message_count: number;
  created_at: string;
};

export type FeedbackThreadDetail = FeedbackThreadItem & {
  messages: FeedbackMessageItem[];
};

export function listFeedback(): Promise<{ threads: FeedbackThreadItem[] }> {
  return apiJson("/feedback");
}

export function getFeedback(threadId: string): Promise<FeedbackThreadDetail> {
  return apiJson(`/feedback/${threadId}`);
}

export function createFeedback(body: {
  title: string;
  category: FeedbackCategory;
  body: string;
}): Promise<FeedbackThreadDetail> {
  return apiJson("/feedback", { method: "POST", body: JSON.stringify(body) });
}

export function addFeedbackMessage(
  threadId: string,
  body: string,
): Promise<FeedbackThreadDetail> {
  return apiJson(`/feedback/${threadId}/messages`, {
    method: "POST",
    body: JSON.stringify({ body }),
  });
}
