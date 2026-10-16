import { ApiError, USER_NETWORK_ERROR, USER_SERVICE_UNAVAILABLE } from "@/lib/api/errors";

export { USER_NETWORK_ERROR, USER_SERVICE_UNAVAILABLE } from "@/lib/api/errors";

const TECHNICAL_MARKERS: RegExp[] = [
  /https?:\/\//i,
  /127\.0\.0\.1/i,
  /localhost/i,
  /\/health\b/i,
  /\/api\/v1/i,
  /ECONNREFUSED/i,
  /ECONNRESET/i,
  /ENOTFOUND/i,
  /ETIMEDOUT/i,
  /failed to proxy/i,
  /fetch failed/i,
  /load failed/i,
  /network error/i,
  /socket hang up/i,
  /unexpected token/i,
  /syntaxerror/i,
  /internal server error/i,
  /^HTTP \d{3}$/i,
  /litellm/i,
  /openai/i,
  /traceback/i,
  /sqlalchemy/i,
  /pydantic/i,
];

const CODE_MESSAGES: Record<string, string> = {
  database_unavailable: "服务暂时繁忙，请稍后重试。",
  forbidden: "您没有权限执行此操作。",
  profile_not_found: "档案不存在或已删除。",
  version_conflict: "档案已被更新，请刷新后重试。",
  unauthorized: "请先登录。",
  validation_error: "提交的信息有误，请检查后重试。",
};

function looksTechnical(message: string): boolean {
  const text = message.trim();
  if (!text) return true;
  if (text.length > 180) return true;
  return TECHNICAL_MARKERS.some((re) => re.test(text));
}

function statusFallback(status: number, fallback: string): string {
  if (status === 401) return "请先登录。";
  if (status === 403) return "您没有权限执行此操作。";
  if (status === 404) return "请求的内容不存在。";
  if (status === 409) return "内容已被更新，请刷新后重试。";
  if (status === 422) return "提交的信息有误，请检查后重试。";
  if (status === 429) return "操作过于频繁，请稍后再试。";
  if (status >= 500) return USER_SERVICE_UNAVAILABLE;
  return fallback;
}

/** Map API / network failures to copy safe for end users (no URLs, health, stack traces). */
export function userFacingApiError(error: unknown, fallback = "操作失败，请稍后重试。"): string {
  if (error instanceof ApiError) {
    if (error.code && CODE_MESSAGES[error.code]) {
      return CODE_MESSAGES[error.code]!;
    }
    const msg = (error.message ?? "").trim();
    if (msg && !looksTechnical(msg)) {
      return msg;
    }
    return statusFallback(error.status, fallback);
  }

  if (error instanceof Error) {
    const msg = error.message.trim();
    if (!msg || looksTechnical(msg)) {
      if (/failed to fetch|load failed|network/i.test(msg)) {
        return USER_NETWORK_ERROR;
      }
      return fallback;
    }
    return msg;
  }

  return fallback;
}

/** Resume export domain hints on top of generic sanitizer. */
export function userFacingExportError(error: unknown): string {
  const raw = error instanceof Error ? error.message : "";
  if (/no resume draft|no bilingual draft/i.test(raw)) {
    return "还没有可导出的优化稿，请先成功生成预览后再审稿/导出。";
  }
  return userFacingApiError(error, "导出失败，请稍后重试。");
}

/** Elevate / bilingual preview. */
export function userFacingElevateError(error: unknown): string {
  const raw = error instanceof Error ? error.message : "";
  if (/ECONNRESET|hang up|Failed to proxy|timeout/i.test(raw)) {
    return "预览请求中断。可先使用中文简历导出，或稍后重试。";
  }
  return userFacingApiError(error, "优化预览失败，请稍后重试。");
}
