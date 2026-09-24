import { apiJson } from "./client";

export type NotificationPriority = "low" | "normal" | "high" | "critical";
export type NotificationType =
  | "system"
  | "email_verify"
  | "profile_action"
  | "parse_quality"
  | "merge_conflict"
  | "export"
  | "agent"
  | "campaign";

export type NotificationAction = {
  label: string;
  href?: string | null;
  action?: string | null;
};

export type NotificationItem = {
  id: string;
  type: NotificationType;
  priority: NotificationPriority;
  title: string;
  body: string;
  created_at: string;
  read: boolean;
  dismissed: boolean;
  dismiss_policy: "manual" | "on_read" | "on_action" | "auto_when_resolved";
  action?: NotificationAction | null;
  metadata: Record<string, string>;
};

export type NotificationListResponse = {
  items: NotificationItem[];
  unread_count: number;
};

export function fetchNotifications(): Promise<NotificationListResponse> {
  return apiJson<NotificationListResponse>("/notifications");
}

export function markNotificationsRead(ids: string[]): Promise<NotificationListResponse> {
  return apiJson<NotificationListResponse>("/notifications/read", {
    method: "POST",
    body: JSON.stringify({ notification_ids: ids }),
  });
}

export function dismissNotifications(ids: string[]): Promise<NotificationListResponse> {
  return apiJson<NotificationListResponse>("/notifications/dismiss", {
    method: "POST",
    body: JSON.stringify({ notification_ids: ids }),
  });
}
