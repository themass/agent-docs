/**
 * What a user reads when a request fails.
 *
 * A user reported 「登录和发密码都报错」 against a form showing 「请求失败」. Those four
 * characters were the fallback for an *unparseable response body*, which happens only
 * when the request never reached our API -- so the one message that named no cause was
 * reserved for the one cause the user cannot diagnose. They retyped a password that was
 * never wrong.
 *
 * The other half of the same bug: the server's messages were English strings written for
 * logs (`Invalid email or password`). `looksTechnical` passes those through, because
 * plain prose carries no URL, no stack frame, no status code.
 *
 * These assertions run against the real `ApiError` and `userFacingApiError`, compiled
 * from source. No browser and no network, so they can run in any environment -- unlike
 * `verify_auth_errors.py`, which drives the actual forms and needs a served build.
 */
import assert from "node:assert/strict";

import { ApiError, USER_SERVICE_UNAVAILABLE, USER_UNREACHABLE } from "./errors.js";
import { userFacingApiError } from "./user-error.js";

/** Latin script with essentially no CJK: an internal string that escaped. */
const LATIN_PROSE = /^[^\u4e00-\u9fff]{12,}$/;

const results = [];

function check(name, fn) {
  try {
    fn();
    results.push(["PASS", name, ""]);
  } catch (error) {
    results.push(["FAIL", name, error.message]);
  }
}

// A refused sign-in states the reason, and the server's log string does not reach the form.
check("refused sign-in is explained in the user's language", () => {
  const msg = userFacingApiError(
    new ApiError(401, { code: "invalid_credentials", message: "Invalid email or password" }),
    "登录失败",
  );
  assert.ok(msg.includes("密码不正确"), msg);
  assert.ok(!msg.includes("Invalid email"), msg);
  assert.ok(!LATIN_PROSE.test(msg), msg);
});

// Endpoints we have not catalogued have no `code`, so the code map cannot help. English
// prose must still be replaced.
check("english prose with no error code is replaced", () => {
  const msg = userFacingApiError(new ApiError(400, { message: "Session user not found" }), "登录失败");
  assert.ok(!msg.includes("Session user not found"), msg);
  assert.ok(/[\u4e00-\u9fff]/.test(msg), msg);
});

// The reported bug: a body that is not our envelope means the request never arrived.
check("unreachable service is named, and not blamed on the user", () => {
  const error = new ApiError(404, {});
  assert.equal(error.serverMessage, undefined, "a non-envelope body must not look like server copy");
  const msg = userFacingApiError(error, "登录失败");
  assert.ok(!msg.includes("请求失败"), msg);
  assert.equal(msg, USER_UNREACHABLE);
  assert.ok(!msg.includes("密码不正确"), msg);
  // The caller's domain fallback must not win: nothing was refused.
  assert.ok(!msg.includes("登录失败"), msg);
});

// A 5xx with no body is our service answering badly, not an unreachable one.
check("5xx with no body is reported as our service", () => {
  assert.equal(userFacingApiError(new ApiError(502, {}), "登录失败"), USER_SERVICE_UNAVAILABLE);
});

// Service copy is Chinese now; the sanitizer must not discard it.
check("chinese copy from the server survives the sanitizer", () => {
  const msg = userFacingApiError(
    new ApiError(400, {
      code: "not_catalogued",
      message: "邮件服务还没配置好，暂时发不出重置邮件，请联系我们。",
    }),
    "操作失败",
  );
  assert.ok(msg.includes("邮件服务"), msg);
});

// Why `invalid_upload` is special: one code covers every reason a file or a pasted
// block cannot become a profile -- wrong type, too large, too short to extract anything
// -- and the difference between them is the entire actionable content. A fixed map entry
// would have to be vague enough to cover all three, which tells the user nothing.
check("rejected ingest keeps the server's specific reason", () => {
  const msg = userFacingApiError(
    new ApiError(400, {
      code: "invalid_upload",
      message: "内容太短了（至少 80 字）。可以粘贴旧简历原文，或写一段你做过什么、带上公司和时间。",
    }),
    "上传失败",
  );
  assert.ok(msg.includes("至少 80 字"), msg);
  assert.ok(msg.includes("公司"), msg);
});

// ...but the specific reason is only preferred while it is usable copy. The upload
// validator still raises English for unsupported extensions, and that must not reach
// the form just because the code opted into server messages.
check("rejected ingest falls back when the reason is not user copy", () => {
  const msg = userFacingApiError(
    new ApiError(400, {
      code: "invalid_upload",
      message: "Unsupported file type '.pages'. Allowed: .doc, .docx, .pdf",
    }),
    "上传失败",
  );
  assert.ok(!msg.includes("Unsupported"), msg);
  assert.ok(/[\u4e00-\u9fff]/.test(msg), msg);
  assert.ok(!LATIN_PROSE.test(msg), msg);
});

check("no entry in the code map is untranslated", () => {
  const codes = [
    "invalid_credentials",
    "email_taken",
    "invalid_password",
    "session_invalid",
    "login_required",
    "guest_required",
    "invalid_token",
    "invalid_verification_code",
    "verification_expired",
    "verification_locked",
    "email_not_configured",
    "invalid_upload",
    "forbidden",
    "profile_not_found",
    "version_conflict",
    "draft_not_found",
    "export_job_not_found",
    "job_not_found",
    "application_not_found",
    "question_not_found",
    "mock_session_not_found",
    "mock_session_closed",
    "unsafe_url",
    "fetch_failed",
    "agent_session_not_found",
    "session_not_found",
    "confirmation_not_found",
    "confirmation_expired",
    "job_save_failed",
    "invalid_request",
    "database_unavailable",
    "validation_error",
  ];
  for (const code of codes) {
    const msg = userFacingApiError(new ApiError(400, { code }), "操作失败");
    assert.ok(/[\u4e00-\u9fff]/.test(msg), `${code}: ${msg}`);
    assert.ok(!LATIN_PROSE.test(msg), `${code}: ${msg}`);
  }
});

for (const [status, name, detail] of results) {
  console.log(`${status}  ${name}${detail ? `  -- ${detail}` : ""}`);
}
const failed = results.filter(([status]) => status === "FAIL").length;
console.log(failed ? `FAIL: ${failed}/${results.length} error-copy checks` : `PASS: ${results.length} error-copy checks`);
process.exit(failed ? 1 : 0);
