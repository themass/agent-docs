import { ApiError, USER_NETWORK_ERROR, type ApiErrorBody } from "@/lib/api/errors";

export { ApiError, type ApiErrorBody } from "@/lib/api/errors";

async function parseApiError(res: Response): Promise<ApiError> {
  let body: ApiErrorBody = {};
  try {
    body = (await res.json()) as ApiErrorBody;
  } catch {
    body = {};
  }
  return new ApiError(res.status, body);
}

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

export async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: "include",
      headers,
    });
  } catch {
    throw new Error(USER_NETWORK_ERROR);
  }
  if (!res.ok) {
    throw await parseApiError(res);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}
