import type { FeedbackStatus } from "@/lib/api/feedback";

const STATUS_LABEL: Record<FeedbackStatus, string> = {
  open: "待处理",
  replying: "已回复",
  resolved: "已解决",
  closed: "已关闭",
};

const STATUS_TONE: Record<FeedbackStatus, string> = {
  open: "badge-warn",
  replying: "badge-brand",
  resolved: "badge-success",
  closed: "badge-neutral",
};

export function FeedbackStatusBadge({ status }: { status: FeedbackStatus }) {
  return <span className={`badge ${STATUS_TONE[status]}`}>{STATUS_LABEL[status]}</span>;
}
