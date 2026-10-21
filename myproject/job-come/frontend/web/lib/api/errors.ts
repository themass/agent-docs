export const USER_NETWORK_ERROR = "无法连接服务，请检查网络后稍后重试。";
export const USER_SERVICE_UNAVAILABLE = "服务暂时不可用，请稍后重试。";

export type ApiErrorBody = {
  code?: string;
  message?: string;
  detail?: string;
};

/**
 * No parseable error body. This is not "the request failed" in any way the user can act
 * on: our own API always answers with `{code, message}`, so a body we cannot read means
 * the request never reached it -- a dev server whose rewrites are not live, a proxy in
 * front of us, a gateway page. Saying 「请求失败」 here sent a user through several rounds
 * of retyping a password that was never the problem.
 */
export const USER_UNREACHABLE = "没能连上服务，请稍后重试；如果一直这样，刷新页面再试一次。";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  /**
   * What the server said, if anything — kept apart from `message` so callers can tell
   * our own fallback copy from text that came off the wire. Only the latter needs
   * sanitizing; running our own copy through a filter for server strings can only
   * throw it away. `undefined` means the response was not our envelope at all.
   */
  readonly serverMessage?: string;

  constructor(status: number, body: ApiErrorBody) {
    const own =
      body.message ?? (typeof body.detail === "string" ? body.detail : undefined);
    const msg = own ?? (status >= 500 ? USER_SERVICE_UNAVAILABLE : USER_UNREACHABLE);
    super(msg);
    this.status = status;
    this.code = body.code;
    this.serverMessage = own;
  }
}
