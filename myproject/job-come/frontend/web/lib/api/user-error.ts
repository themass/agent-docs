import { ApiError, USER_NETWORK_ERROR, USER_SERVICE_UNAVAILABLE } from "@/lib/api/errors";

export {
  USER_NETWORK_ERROR,
  USER_SERVICE_UNAVAILABLE,
  USER_UNREACHABLE,
} from "@/lib/api/errors";

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

/**
 * Server `code` -> user-facing copy. This is the reliable layer: it does not depend on
 * the server's own wording, so an error message written in English for a log cannot
 * reach the user through it. `looksTechnical` does not catch those — plain English prose
 * carries none of its markers, which is how 「Invalid email or password」 ended up on the
 * login form.
 *
 * Service messages are user-facing Chinese now, so this map is a second line of defence
 * rather than the only one. Keep both: the copy here can be more specific about what to
 * do next than an exception message written at the point of failure.
 */
const CODE_MESSAGES: Record<string, string> = {
  // Account & session
  invalid_credentials: "邮箱或密码不正确，请重新输入。",
  email_taken: "这个邮箱已经注册过了，可以直接登录或用「忘记密码」找回。",
  invalid_password: "当前密码不正确。",
  session_invalid: "登录状态已失效，请重新登录。",
  login_required: "请先登录后再继续。",
  unauthorized: "请先登录。",
  guest_required: "请先创建访客会话。",
  guest_session_required: "请先创建访客会话。",
  // Email verification & password reset
  invalid_token: "链接无效或已过期，请重新发起。",
  invalid_verification_code: "验证码不正确，请检查邮件里的 4 位数字。",
  verification_expired: "验证码已过期，请重新发送验证邮件。",
  verification_locked: "验证码输错次数过多，请重新发送验证邮件。",
  email_not_configured: "邮件服务还没配置好，暂时发不出邮件，请联系我们。",
  // Profile
  invalid_upload: "这份内容暂时没法建档，请换一个文件或多写一些内容再试。",
  forbidden: "您没有权限执行此操作。",
  profile_not_found: "档案不存在或已删除。",
  version_conflict: "档案已被更新，请刷新后重试。",
  // Resume drafts & exports
  draft_not_found: "没找到这份优化稿，请先重新生成预览。",
  export_job_not_found: "没找到这次导出任务，请重新导出一次。",
  // Jobs, applications, interviews
  job_not_found: "职位不存在或已删除。",
  application_not_found: "投递记录不存在或已删除。",
  question_not_found: "题目不存在或已删除。",
  mock_session_not_found: "模拟面试不存在或已删除。",
  mock_session_closed: "这场模拟面试已经结束了。",
  unsafe_url: "这个链接地址不被支持，请改用公开网页地址。",
  fetch_failed: "没能读取这个链接，请改为直接粘贴 JD 原文。",
  // Agent
  agent_session_not_found: "会话不存在或已删除。",
  session_not_found: "会话不存在或已删除。",
  confirmation_not_found: "没找到这条待确认的改动，可能已经处理过了。",
  confirmation_stale: "简历已更新，为避免覆盖，请让舟卡基于最新简历重新生成修改确认。",
  confirmation_superseded: "这条修改已被更新的卡片取代，请确认对话里最新一张修改卡片。",
  confirmation_processed: "这条修改已经处理，请刷新会话查看结果。",
  confirmation_unrecoverable: "旧确认缺少版本信息，请让舟卡重新生成修改确认。",
  confirmation_rejected: "这条修改已被拒绝，请让舟卡重新生成修改确认。",
  confirmation_applied: "这条修改已保存；如需撤销，请使用简历版本历史。",
  confirmation_expired: "这条确认已过期，请重新发起。",
  job_save_failed: "职位没保存成功，请稍后重试。",
  attachment_too_large: "附件太大了，请压缩图片或分几条消息发送。",
  attachment_rejected: "这个附件暂时发不了，舟卡只支持图片和语音，文档请用上传简历入口。",
  invalid_request: "提交的信息有误，请检查后重试。",
  // Infrastructure
  database_unavailable: "服务暂时繁忙，请稍后重试。",
  validation_error: "提交的信息有误，请检查后重试。",
};

/**
 * Codes whose server message is more useful than any fixed copy we could write here.
 *
 * `invalid_upload` covers every reason a file or a pasted block cannot become a
 * profile — wrong extension, too large, too short to extract anything — and the
 * difference between them is the whole of what the user needs to hear. The entry in
 * `CODE_MESSAGES` stays as the floor for when the message is unusable.
 */
const CODE_PREFERS_SERVER_MESSAGE = new Set<string>(["invalid_upload"]);

/**
 * Latin-script prose with no technical markers. `looksTechnical` exists to catch stack
 * traces and URLs; an English sentence is neither, but it is still not copy we would
 * show a Chinese-speaking user. Anything essentially free of CJK is treated as internal.
 */
function looksForeign(message: string): boolean {
  const letters = message.replace(/[^\p{L}]/gu, "");
  if (letters.length === 0) return false;
  const cjk = letters.match(/[\u4e00-\u9fff]/g)?.length ?? 0;
  return cjk / letters.length < 0.2;
}

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
    const detail = error.serverMessage?.trim();
    if (
      error.code &&
      CODE_PREFERS_SERVER_MESSAGE.has(error.code) &&
      detail &&
      !looksTechnical(detail) &&
      !looksForeign(detail)
    ) {
      return detail;
    }
    if (error.code && CODE_MESSAGES[error.code]) {
      return CODE_MESSAGES[error.code]!;
    }
    // Only text from the wire gets sanitized. With no server message the request never
    // reached our API, so the caller's domain fallback ("登录失败") would be a guess
    // about a request that was not refused — and `ApiError` has already picked copy that
    // says so.
    if (!detail) {
      return error.message;
    }
    if (!looksTechnical(detail) && !looksForeign(detail)) {
      return detail;
    }
    return statusFallback(error.status, fallback);
  }

  if (error instanceof Error) {
    const msg = error.message.trim();
    if (!msg || looksTechnical(msg) || looksForeign(msg)) {
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

/**
 * Sanitizer for an agent **error** string — a failure message, never a reply.
 *
 * Deliberately aggressive: it leans on `looksTechnical` (which treats anything over
 * 180 chars as a stack trace) and `looksForeign` (which treats low-CJK text as
 * internal), because an error path has no legitimate reason to produce long or
 * English text for a Chinese-speaking user.
 *
 * Do NOT use this on assistant replies. It was previously wired up as
 * `formatAssistantMessage` as well, and the 180-char rule inside `looksTechnical`
 * then rewrote *every* normal reply longer than 180 characters into
 * 「舟卡没能完成这次回复」 — which, on a resume-editing product where a useful answer is
 * always several hundred characters, meant a successful run was reported as a failure
 * essentially every time. `userFacingAssistantText` below is the one for replies.
 */
export function userFacingAgentMessage(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return trimmed;
  if (!looksTechnical(trimmed) && !looksForeign(trimmed)) {
    return trimmed;
  }
  if (
    /unavailable|provider|configured llm|multiple retries|rate limit|timeout/i.test(trimmed)
  ) {
    return "舟卡暂时忙不过来，请稍后再试或重新发送。";
  }
  return "舟卡没能完成这次回复，请换个说法再试一次。";
}

/**
 * Leak guard for assistant **reply** text.
 *
 * A reply is content the user asked for, so the default is to pass it through
 * untouched. Length is not a signal here (a rewritten experience section runs to
 * hundreds of characters) and neither is script (the user can ask for an English
 * resume, which is legitimately CJK-free) — the two rules that made the old shared
 * sanitizer unusable for this job.
 *
 * What is still worth blocking is an infrastructure detail that escaped into prose:
 * an internal URL, a stack trace, a provider/ORM name. Those indicate the model was
 * handed something it should not have been, and showing them would leak our stack.
 * When one appears the whole reply is replaced rather than patched, because a reply
 * that contains a traceback is not a reply worth showing in part.
 */
const ASSISTANT_LEAK_MARKERS: RegExp[] = [
  /https?:\/\//i,
  /127\.0\.0\.1/i,
  /localhost/i,
  /\/api\/v1/i,
  /ECONNREFUSED|ECONNRESET|ENOTFOUND|ETIMEDOUT/i,
  /traceback \(most recent call last\)/i,
  /litellm/i,
  /sqlalchemy/i,
];

export function userFacingAssistantText(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return trimmed;
  if (ASSISTANT_LEAK_MARKERS.some((re) => re.test(trimmed))) {
    return "舟卡没能完成这次回复，请换个说法再试一次。";
  }
  return trimmed;
}

/** Elevate / bilingual preview. */
export function userFacingElevateError(error: unknown): string {
  if (error instanceof DOMException && error.name === "AbortError") {
    return "生成时间过长，请求已取消。请点「重新生成」再试一次；若反复失败，可稍后再试。";
  }
  const raw = error instanceof Error ? error.message : "";
  if (/ECONNRESET|hang up|Failed to proxy|timeout|aborted/i.test(raw)) {
    return "预览请求中断。请点「重新生成」再试；中文稿若已生成过，导出仍可用上次成功的预览。";
  }
  return userFacingApiError(error, "优化预览失败，请稍后重试。");
}
