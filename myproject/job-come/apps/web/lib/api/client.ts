export type ApiErrorBody = {
  code?: string;
  message?: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message ?? `HTTP ${status}`);
    this.status = status;
    this.code = body.code;
  }
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

async function parseApiError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    body = { message: res.statusText };
  }
  return new ApiError(res.status, body);
}

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!res.ok) {
    throw await parseApiError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
