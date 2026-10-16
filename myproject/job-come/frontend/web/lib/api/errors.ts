export const USER_NETWORK_ERROR = "无法连接服务，请检查网络后稍后重试。";
export const USER_SERVICE_UNAVAILABLE = "服务暂时不可用，请稍后重试。";

export type ApiErrorBody = {
  code?: string;
  message?: string;
  detail?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, body: ApiErrorBody) {
    const msg =
      body.message ??
      (typeof body.detail === "string" ? body.detail : undefined) ??
      (status >= 500 ? USER_SERVICE_UNAVAILABLE : "请求失败");
    super(msg);
    this.status = status;
    this.code = body.code;
  }
}
